import json
from pathlib import Path

import duckdb

from bench.gen.static import WKB_POINT

DOCUMENTS = Path(__file__).with_name("documents.sql")
COLLECTIONS = ("lockermats", "tariffs", "customers", "orders", "incidents", "auditEvents", "shipLinks")
BATCH = 50_000


def point_coordinates(ewkb):
    return list(WKB_POINT.unpack(ewkb)[-2:])


def transform(source, destination):
    tables = json.loads((source / "manifest.json").read_text())["counts"]
    destination.mkdir(parents=True, exist_ok=True)
    counts = {}
    with duckdb.connect() as db:
        db.create_function("point_coordinates", point_coordinates, ["BLOB"], "DOUBLE[]")
        for table in tables:
            db.execute(f"create view {table} as select * from read_parquet('{source / table}.parquet')")
        db.execute(DOCUMENTS.read_text())
        for collection in COLLECTIONS:
            counts[collection] = 0
            reader = db.sql(f"select document from {collection} order by id_").to_arrow_reader(BATCH)
            with (destination / f"{collection}.json").open("w", encoding="utf-8") as file:
                for batch in reader:
                    documents = batch.column(0).to_pylist()
                    file.writelines(f"{document}\n" for document in documents)
                    counts[collection] += len(documents)
    return counts
