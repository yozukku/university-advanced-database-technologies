import io
import json
import re
import time
from pathlib import Path

import duckdb
import psycopg
import pyarrow.csv as csv

DDL = Path("bench/ddl/pg")
INDEX = re.compile(r"create index (\w+)")
SERVER = "host=pg user=bench password=bench"
DATABASE = "bagazomat"
BATCH = 100_000
CSV = csv.WriteOptions(include_header=False)
TEXT = {"bytea": "'\\x' || hex({})", "geometry": "hex({})"}
COLUMNS = """
    select a.attname, t.typname
    from pg_attribute a join pg_type t on t.oid = a.atttypid
    where a.attrelid = %s::regclass and a.attnum > 0 and not a.attisdropped and a.attgenerated = ''
    order by a.attnum
"""


def setting(conn, name):
    return conn.execute("select current_setting(%s)", (name,)).fetchone()[0]


def connect(dbname=DATABASE):
    conn = psycopg.connect(f"{SERVER} dbname={dbname}", autocommit=True)
    timeout = setting(conn, "statement_timeout")
    if timeout != "0":
        conn.close()
        raise RuntimeError(f"statement_timeout is {timeout}, expected 0")
    return conn


def recreate(dbname=DATABASE):
    with connect("postgres") as conn:
        conn.execute(f"drop database if exists {dbname} with (force)")
        conn.execute(f"create database {dbname}")


def run_script(conn, name):
    conn.execute((DDL / name).read_text())


def copy_table(conn, parquet, path, table):
    columns = conn.execute(COLUMNS, (table,)).fetchall()
    names = ", ".join(column for column, _ in columns)
    select = ", ".join(TEXT.get(kind, "{}").format(column) for column, kind in columns)
    batches = parquet.sql(f"select {select} from read_parquet('{path}')").to_arrow_reader(BATCH)
    with conn.cursor() as cursor:
        with cursor.copy(f"copy {table} ({names}) from stdin (format csv, freeze)") as copy:
            for batch in batches:
                buffer = io.BytesIO()
                csv.write_csv(batch, buffer, CSV)
                copy.write(buffer.getbuffer())
        return cursor.rowcount


def load(directory):
    counts = json.loads((directory / "manifest.json").read_text())["counts"]
    recreate()
    timings = {}
    with connect() as conn, duckdb.connect() as parquet:
        parquet.execute("set timezone = 'UTC'")
        start = time.perf_counter()
        with conn.transaction():
            run_script(conn, "base/tables.sql")
            for table, expected in counts.items():
                copied = copy_table(conn, parquet, directory / f"{table}.parquet", table)
                if copied != expected:
                    raise ValueError(f"{table}: copied {copied} rows, expected {expected}")
        timings["copy"] = time.perf_counter() - start
        start = time.perf_counter()
        run_script(conn, "base/constraints.sql")
        run_script(conn, "base/fk_support.sql")
        timings["base"] = time.perf_counter() - start
        start = time.perf_counter()
        conn.execute("vacuum (freeze, analyze)")
        timings["vacuum"] = time.perf_counter() - start
        timeout = setting(conn, "statement_timeout")
    return counts, timings, timeout


def timed(conn, statement):
    start = time.perf_counter()
    conn.execute(statement)
    return time.perf_counter() - start


def apply_index(conn):
    built = {}
    for statement in (DDL / "idx/indexes.sql").read_text().split(";"):
        if statement.strip():
            built[INDEX.search(statement)[1]] = timed(conn, statement)
    return built, {statement: timed(conn, statement) for statement in ("analyze audit_event_", "vacuum")}
