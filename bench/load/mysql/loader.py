import json
import tempfile
import time
from pathlib import Path

import duckdb
import mysql.connector

from bench.gen.static import WKB_POINT

DDL = Path("bench/ddl/mysql")
SERVER = {"host": "mysql", "user": "root", "password": "bench-root", "allow_local_infile": True, "autocommit": True}
DATABASE = "bagazomat"
COLUMNS = """
    select column_name, data_type, character_maximum_length
    from information_schema.columns
    where table_schema = %s and table_name = %s and generation_expression = ''
    order by ordinal_position
"""
STATS = "select table_name from mysql.innodb_table_stats where database_name = %s"
SELECT = {"datetime": "{}::timestamp", "binary": "hex({})", "point": "wkt({})"}
SET = {"binary": "{0} = unhex(@{0})", "point": "{0} = st_geomfromtext(@{0}, 4326, 'axis-order=long-lat')"}
DERIVED = {
    "changes_new_": "to_json(list_transform(list_filter(json_extract(changes_, '$[*]'), "
                    "lambda e: json_type(e, '$.new') = 'VARCHAR'), lambda e: json_extract_string(e, '$.new')))",
}
CSV = "format csv, header false, quote '\"', escape '\"', nullstr 'NULL', force_quote *"
LOAD = """
    load data local infile '{path}' into table {table} character set utf8mb4
    fields terminated by ',' optionally enclosed by '"' escaped by ''
    ({columns}) {assignments}
"""


def wkt(point):
    return "POINT({} {})".format(*WKB_POINT.unpack(point)[-2:])


def transformer():
    parquet = duckdb.connect()
    parquet.execute("set timezone = 'UTC'")
    parquet.create_function("wkt", wkt, ["BLOB"], "VARCHAR")
    return parquet


def statements(script):
    delimiter, lines = ";", []
    for line in script.splitlines():
        if line.lower().startswith("delimiter "):
            delimiter = line.split()[1]
            continue
        lines.append(line)
        if line.rstrip().endswith(delimiter):
            statement = "\n".join(lines).rstrip().removesuffix(delimiter).strip()
            lines = []
            if statement:
                yield statement


def fetch(cursor, statement, params=()):
    cursor.execute(statement, params)
    return cursor.fetchall() if cursor.with_rows else []


def run_script(cursor, name):
    for statement in statements((DDL / name).read_text()):
        fetch(cursor, statement)


def write_csv(parquet, path, columns, target):
    for name, kind, length in columns:
        if kind == "binary":
            wrong = parquet.execute(f"select count(*) from read_parquet('{path}') where octet_length({name}) <> {length}")
            if count := wrong.fetchone()[0]:
                raise ValueError(f"{path.stem}.{name}: {count} values are not {length} bytes long")
    select = ", ".join(DERIVED[name] if name in DERIVED else SELECT.get(kind, "{}").format(name) for name, kind, _ in columns)
    parquet.execute(f"copy (select {select} from read_parquet('{path}')) to '{target}' ({CSV})")


def load_table(cursor, parquet, path, table, scratch):
    columns = fetch(cursor, COLUMNS, (DATABASE, table))
    target = scratch / f"{table}.csv"
    write_csv(parquet, path, columns, target)
    names = ", ".join(f"@{name}" if kind in SET else name for name, kind, _ in columns)
    assignments = ", ".join(SET[kind].format(name) for name, kind, _ in columns if kind in SET)
    cursor.execute(LOAD.format(path=target, table=table, columns=names, assignments=f"set {assignments}" if assignments else ""))
    loaded = cursor.rowcount
    warnings = fetch(cursor, "show warnings limit 5")
    target.unlink()
    if warnings:
        raise ValueError(f"{table}: {warnings}")
    return loaded


def load(directory):
    counts = json.loads((directory / "manifest.json").read_text())["counts"]
    timings = {}
    with (mysql.connector.connect(**SERVER) as conn, conn.cursor() as cursor, transformer() as parquet,
          tempfile.TemporaryDirectory() as scratch):
        fetch(cursor, f"drop database if exists {DATABASE}")
        fetch(cursor, f"create database {DATABASE}")
        fetch(cursor, f"use {DATABASE}")
        start = time.perf_counter()
        run_script(cursor, "base/tables.sql")
        fetch(cursor, "set unique_checks = 0")
        for table, expected in counts.items():
            loaded = load_table(cursor, parquet, directory / f"{table}.parquet", table, Path(scratch))
            if loaded != expected:
                raise ValueError(f"{table}: loaded {loaded} rows, expected {expected}")
        fetch(cursor, "set unique_checks = 1")
        timings["data"] = time.perf_counter() - start
        start = time.perf_counter()
        fetch(cursor, "set foreign_key_checks = 0")
        run_script(cursor, "base/foreign_keys.sql")
        fetch(cursor, "set foreign_key_checks = 1")
        timings["foreign keys"] = time.perf_counter() - start
        start = time.perf_counter()
        run_script(cursor, "base/indexes.sql")
        run_script(cursor, "base/triggers.sql")
        timings["indexes"] = time.perf_counter() - start
        start = time.perf_counter()
        analyzed = fetch(cursor, f"analyze table {', '.join(counts)}")
        failed = [row for row in analyzed if row[2] != "status" or row[3] != "OK"]
        if failed:
            raise ValueError(f"analyze table: {failed}")
        timings["analyze"] = time.perf_counter() - start
        missing = set(counts) - {table for table, in fetch(cursor, STATS, (DATABASE,))}
        if missing:
            raise ValueError(f"mysql.innodb_table_stats has no row for {sorted(missing)}")
    return counts, timings
