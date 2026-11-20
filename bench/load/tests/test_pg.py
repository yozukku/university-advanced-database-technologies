import json
import unittest
from pathlib import Path

from bench.load.pg.loader import DDL, connect, recreate

SCHEMA = Path("docs/design/schema.sql")
INDEXES = Path("docs/bench/indexes.yaml")
FK_SUPPORT = ("reservation_cell_fk_support", "opening_access_code_fk_support")
CATALOG = {
    "relations": """
        select relname, relkind::text, relpersistence::text
        from pg_class where relnamespace = 'public'::regnamespace
    """,
    "columns": """
        select c.relname, a.attnum, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
               a.attgenerated::text, a.attidentity::text, pg_get_expr(d.adbin, d.adrelid),
               a.attcollation::regcollation::text
        from pg_attribute a
        join pg_class c on c.oid = a.attrelid
        left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
        where c.relnamespace = 'public'::regnamespace and c.relkind in ('r', 'v')
          and a.attnum > 0 and not a.attisdropped
    """,
    "constraints": """
        select c.relname, k.conname, k.contype::text, pg_get_constraintdef(k.oid), k.condeferrable,
               k.condeferred, k.convalidated, k.conindid::regclass::text
        from pg_constraint k join pg_class c on c.oid = k.conrelid
        where c.relnamespace = 'public'::regnamespace
    """,
    "indexes": "select tablename, indexname, indexdef from pg_indexes where schemaname = 'public'",
    "sequences": """
        select sequencename, data_type::text, start_value, min_value, max_value, increment_by, cycle, cache_size
        from pg_sequences where schemaname = 'public'
    """,
    "extensions": "select extname, extversion from pg_extension",
}


def catalog(dbname, *scripts):
    recreate(dbname)
    try:
        with connect(dbname) as conn:
            for script in scripts:
                conn.execute(script)
            return {name: set(conn.execute(query).fetchall()) for name, query in CATALOG.items()}
    finally:
        with connect("postgres") as conn:
            conn.execute(f"drop database {dbname} with (force)")


def fk_support_indexes():
    extras = json.loads(INDEXES.read_text())["base_extras"]
    return {(item["scope"], item["name"], f"CREATE INDEX {item['name']} ON public.{item['scope']} USING btree "
                                         f"({', '.join(item['keys'])})")
            for key in FK_SUPPORT for item in extras[key]["pg"]}


class CatalogTest(unittest.TestCase):
    def test_base_without_fk_support_equals_schema(self):
        tables, constraints, fk_support = ((DDL / "base" / name).read_text()
                                           for name in ("tables.sql", "constraints.sql", "fk_support.sql"))
        schema = catalog("catalog_schema_", SCHEMA.read_text())
        base = catalog("catalog_base_", tables, constraints)
        for name in CATALOG:
            with self.subTest(name):
                self.assertSetEqual(schema[name], base[name])

        full = catalog("catalog_base_", tables, constraints, fk_support)
        indexes = fk_support_indexes()
        expected = {name: set() for name in CATALOG}
        expected["indexes"] = indexes
        expected["relations"] = {(index, "i", "p") for _, index, _ in indexes}
        self.assertEqual(len(indexes), 2)
        self.assertEqual({name: full[name] - base[name] for name in CATALOG}, expected)
        self.assertEqual({name: base[name] - full[name] for name in CATALOG}, {name: set() for name in CATALOG})


if __name__ == "__main__":
    unittest.main()
