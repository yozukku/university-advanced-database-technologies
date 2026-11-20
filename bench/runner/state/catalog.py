import json
import re
from pathlib import Path

import docker
import mysql.connector
from neo4j import GraphDatabase

from bench.check.verify.canonical import TABLES
from bench.load.mongo import loader as mongo_loader
from bench.load.mysql import loader as mysql_loader
from bench.load.neo4j import loader as neo4j_loader
from bench.load.pg import loader as pg_loader

from .containers import engine_container

MAP = Path("docs/bench/indexes.yaml")
UNMAPPED = {"edge", "label", "column"}
PRESENCE_ONLY = {"validator"}
VOLATILE = {"bytes", "state"}
PG_KINDS = {"p": "primary", "u": "unique", "f": "foreign key", "c": "check", "x": "exclude"}
PG_INDEXED = {"primary", "unique", "exclude", "btree", "gist", "gin"}
PG_CONSTRAINTS = """
    select t.relname, c.conname, c.contype, c.conindid,
           array(select a.attname from unnest(c.conkey) with ordinality k(n, o)
                 join pg_attribute a on a.attrelid = c.conrelid and a.attnum = k.n order by k.o)
    from pg_constraint c join pg_class t on t.oid = c.conrelid
    where t.relnamespace = 'public'::regnamespace and t.relname = any(%s)
"""
PG_INDEXES = """
    select x.indexrelid, t.relname, i.relname, am.amname, x.indisunique, x.indpred is not null,
           array(select pg_get_indexdef(x.indexrelid, k, true)
                        || case when x.indoption[k - 1] & 1 = 1 then ' desc' else '' end
                 from generate_series(1, x.indnatts) k order by k),
           pg_relation_size(x.indexrelid)
    from pg_index x join pg_class i on i.oid = x.indexrelid join pg_class t on t.oid = x.indrelid
    join pg_am am on am.oid = i.relam
    where t.relnamespace = 'public'::regnamespace and t.relname = any(%s)
"""
MYSQL_INDEXES = """
    select table_name, index_name, column_name, expression, collation, non_unique, index_type
    from information_schema.statistics where table_schema = %s order by table_name, index_name, seq_in_index
"""
MYSQL_CONSTRAINTS = """
    select c.table_name, c.constraint_name, c.constraint_type, k.column_name
    from information_schema.table_constraints c
    left join information_schema.key_column_usage k
      on k.constraint_schema = c.constraint_schema and k.table_name = c.table_name and k.constraint_name = c.constraint_name
    where c.table_schema = %s and c.constraint_type in ('FOREIGN KEY', 'CHECK')
    order by c.table_name, c.constraint_name, k.ordinal_position
"""
MYSQL_TRIGGERS = """
    select event_object_table, trigger_name, lower(concat(action_timing, ' ', event_manipulation))
    from information_schema.triggers where trigger_schema = %s
"""
MYSQL_TABLES = "select table_name from information_schema.tables where table_schema = %s and table_type = 'BASE TABLE'"
MYSQL_SIZES = """
    select table_name, index_name, stat_value * @@innodb_page_size
    from mysql.innodb_index_stats where database_name = %s and stat_name = 'size'
"""
MYSQL_KINDS = {"SPATIAL": "spatial", "FULLTEXT": "fulltext"}
NEO4J_INDEXES = """
    SHOW INDEXES YIELD id, name, state, type, entityType, labelsOrTypes, properties, owningConstraint, indexProvider
"""
NEO4J_CONSTRAINTS = "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties, ownedIndex"
NEO4J_LOOKUPS = {"NODE": ("nodes", "node_label_lookup"), "RELATIONSHIP": ("relationships", "relationship_type_lookup")}
NEO4J_INDEX_DIRECTORY = "/data/databases/neo4j/schema/index"


def sql_key(key):
    text = re.sub(r"[`\\]", "", key.lower())
    text = re.sub(r"::(?:text|character varying)\b|_utf8mb4(?=')", "", text)
    text = re.sub(r"\s+\w+_ops$", "", text)
    text = re.sub(r"(\w+)\s*->>\s*('[^']*')", r"json_unquote(json_extract(\1,\2))", text)
    return re.sub(r"[\s()]", "", text.replace("character set", "charset"))


def comparable(engine, entry):
    item = {field: value for field, value in entry.items() if field not in VOLATILE}
    if engine in ("pg", "mysql"):
        item["keys"] = [sql_key(key) for key in item["keys"]]
    return item


def add(catalog, scope, name, kind, **entry):
    catalog[(scope, name, kind)] = entry


def read_pg():
    catalog = {}
    with pg_loader.connect() as conn:
        indexes = {row[0]: row[1:] for row in conn.execute(PG_INDEXES, (list(TABLES),))}
        for scope, name, kind, index, keys in conn.execute(PG_CONSTRAINTS, (list(TABLES),)):
            kind = PG_KINDS[kind]
            if kind in PG_INDEXED:
                *_, partial, keys, size = indexes.pop(index)
                add(catalog, scope, name, kind, keys=keys, predicate=partial, bytes=size)
            else:
                add(catalog, scope, name, kind, keys=keys if kind == "foreign key" else [])
        for scope, name, method, unique, partial, keys, size in indexes.values():
            add(catalog, scope, name, "unique" if unique else method, keys=keys, predicate=partial, bytes=size)
    return catalog


def mysql_kind(name, index_type, expressions, unique):
    if name == "PRIMARY":
        return "primary"
    if index_type in MYSQL_KINDS:
        return MYSQL_KINDS[index_type]
    if any(expression and " array)" in expression for expression in expressions):
        return "multi_valued"
    if any(expressions):
        return "functional"
    return "unique" if unique else "btree"


def read_mysql():
    catalog = {}
    database = mysql_loader.DATABASE
    with mysql.connector.connect(**mysql_loader.SERVER, database=database) as conn, conn.cursor() as cursor:
        fetch = mysql_loader.fetch
        sizes = {(scope, name): int(size) for scope, name, size in fetch(cursor, MYSQL_SIZES, (database,))}
        indexes = {}
        for scope, name, column, expression, collation, non_unique, index_type in fetch(cursor, MYSQL_INDEXES, (database,)):
            index = indexes.setdefault((scope, name), {"type": index_type, "unique": not non_unique, "keys": [], "expressions": []})
            index["keys"].append((column or expression) + (" desc" if collation == "D" else ""))
            index["expressions"].append(expression)
        for (scope, name), index in indexes.items():
            kind = mysql_kind(name, index["type"], index["expressions"], index["unique"])
            extra = {"unique": index["unique"]} if kind == "functional" else {}
            add(catalog, scope, name, kind, keys=index["keys"], bytes=sizes.get((scope, name)), **extra)
        constraints = {}
        for scope, name, kind, column in fetch(cursor, MYSQL_CONSTRAINTS, (database,)):
            keys = constraints.setdefault((scope, name, kind.lower()), [])
            if kind == "FOREIGN KEY":
                keys.append(column)
        for (scope, name, kind), keys in constraints.items():
            add(catalog, scope, name, kind, keys=keys)
        for scope, name, event in fetch(cursor, MYSQL_TRIGGERS, (database,)):
            add(catalog, scope, name, "trigger", keys=[], event=event)
        for (table,) in fetch(cursor, MYSQL_TABLES, (database,)):
            if table not in TABLES:
                add(catalog, table, table, "table", keys=[])
    return catalog


def read_mongo():
    catalog = {}
    with mongo_loader.connect() as client:
        db = client[mongo_loader.DATABASE]
        for collection in db.list_collections():
            scope = collection["name"]
            if (collection.get("options") or {}).get("validator"):
                add(catalog, scope, "$jsonSchema", "validator", keys=[])
            [stats] = db[scope].aggregate([{"$collStats": {"storageStats": {}}}])
            for index in db[scope].list_indexes():
                key = index["key"]
                if index["name"] == "_id_":
                    kind = "primary"
                elif index.get("unique"):
                    kind = "unique"
                else:
                    kind = "2dsphere" if "2dsphere" in key.values() else "btree"
                keys = [f"{field} desc" if direction == -1 else field for field, direction in key.items()]
                predicate = json.loads(json.dumps(index.get("partialFilterExpression")))
                add(catalog, scope, index["name"], kind, keys=keys, predicate=predicate,
                    bytes=stats["storageStats"]["indexSizes"][index["name"]])
    return catalog


def neo4j_sizes():
    container = engine_container(docker.from_env(), "neo4j")
    code, output = container.exec_run(["sh", "-c", f"du -sb {NEO4J_INDEX_DIRECTORY}/*/*"])
    if code:
        raise RuntimeError(output.decode())
    return {int(path.rsplit("/", 1)[1]): int(size) for size, path in (line.split() for line in output.decode().splitlines())}


def read_neo4j():
    catalog = {}
    sizes = neo4j_sizes()
    with (GraphDatabase.driver(neo4j_loader.URI, auth=neo4j_loader.AUTH, notifications_min_severity="OFF") as driver,
          driver.session(database="neo4j") as session):
        indexes = {row["name"]: row for row in session.run(NEO4J_INDEXES).data()}
        for row in session.run(NEO4J_CONSTRAINTS).data():
            owned = indexes.pop(row["ownedIndex"])
            kind = "unique" if row["type"] == "UNIQUENESS" else row["type"].lower()
            add(catalog, row["labelsOrTypes"][0], row["name"], kind, keys=row["properties"],
                bytes=sizes.get(owned["id"]), state=owned["state"])
        for row in indexes.values():
            if row["type"] == "LOOKUP":
                scope, name = NEO4J_LOOKUPS[row["entityType"]]
                keys = []
            else:
                scope, name, keys = row["labelsOrTypes"][0], row["name"], row["properties"]
            add(catalog, scope, name, row["type"].lower(), keys=keys, bytes=sizes.get(row["id"]), state=row["state"])
    return catalog


READERS = {"pg": read_pg, "mysql": read_mysql, "mongo": read_mongo, "neo4j": read_neo4j}


def read(engine):
    return READERS[engine]()


def listed(entry, engine):
    value = entry[engine]
    return value if isinstance(value, list) else []


def described(engine, obj):
    kind = "btree" if engine == "mongo" and obj["kind"] == "multikey" else obj["kind"]
    entry = {"keys": obj.get("keys", [])}
    if engine == "pg" and kind in PG_INDEXED:
        entry["predicate"] = bool(obj.get("predicate"))
    if engine == "mongo" and kind != "validator":
        entry["predicate"] = obj.get("predicate")
    if engine == "mysql" and kind == "functional":
        entry["unique"] = obj.get("unique", False)
    if kind == "trigger":
        entry["event"] = obj["event"]
    return (obj["scope"], obj["name"], kind), entry


def expected(engine, config):
    plan = json.loads(MAP.read_text())
    if config == "idx":
        objects = [obj for row in plan["idx"].values() for obj in listed(row["engines"], engine)]
    else:
        objects = [obj for entry in [*plan["base"].values(), *plan["base_extras"].values()] for obj in listed(entry, engine)]
        objects += list(plan["mysql_fk_support"].values()) if engine == "mysql" else []
    return dict(described(engine, obj) for obj in objects if obj["kind"] not in UNMAPPED)


def label(key):
    scope, name, kind = key
    return f"{kind} {scope}.{name}"


def compare(engine, catalog, wanted):
    problems = [f"missing {label(key)}" for key in sorted(wanted.keys() - catalog.keys())]
    problems += [f"unexpected {label(key)}" for key in sorted(catalog.keys() - wanted.keys()) if key[2] not in PRESENCE_ONLY]
    for key in sorted(wanted.keys() & catalog.keys()):
        found, needed = comparable(engine, catalog[key]), comparable(engine, wanted[key])
        if found != needed:
            problems.append(f"{label(key)} is {found}, expected {needed}")
    problems += [f"{label(key)} is {entry['state']}" for key, entry in sorted(catalog.items())
                 if entry.get("state", "ONLINE") != "ONLINE"]
    return problems


def added(engine, base, idx):
    problems = [f"IDX changed {label(key)}" for key in sorted(base)
                if key not in idx or comparable(engine, idx[key]) != comparable(engine, base[key])]
    return {key: idx[key] for key in idx.keys() - base.keys()}, problems


def listing(catalog):
    return [{"scope": scope, "name": name, "kind": kind, **entry} for (scope, name, kind), entry in sorted(catalog.items())]
