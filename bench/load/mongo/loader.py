import json
import os
import socket
import time
from collections import Counter
from pathlib import Path

import docker
from pymongo import MongoClient

from bench.transform.mongo.transform import COLLECTIONS, transform

DDL = Path("bench/ddl/mongo")
URI = "mongodb://mongo:27017/?directConnection=true"
DATABASE = "bagazomat"
WORKSPACE = "/workspace"
IMPORT_CPUS = 4_000_000_000


def size(array):
    return {"$size": {"$ifNull": [array, []]}}


def total(array, name, expression):
    return {"$sum": {"$map": {"input": {"$ifNull": [array, []]}, "as": name, "in": expression}}}


COUNTS = {
    "lockermats": {"lockermat_": 1, "lockermat_cell_": size("$cells"), "lockermat_opening_hours_": size("$openingHours")},
    "tariffs": {"tariff_": 1},
    "customers": {"customer_": 1},
    "orders": {
        "order_": 1,
        "shipment_": {"$cond": [{"$eq": [{"$type": "$shipment"}, "object"]}, 1, 0]},
        "reservation_": size("$reservations"),
        "access_code_": total("$reservations", "leg", size("$$leg.accessCodes")),
        "cell_opening_": total("$reservations", "leg", total("$$leg.accessCodes", "code", size("$$code.openings"))),
        "payment_": size("$payments"),
    },
    "incidents": {"incident_": 1, "cell_opening_": size("$serviceOpenings")},
    "auditEvents": {"audit_event_": 1},
    "shipLinks": {"shipLinks": 1},
}


def connect():
    return MongoClient(URI)


def run_script(db, name):
    for command in json.loads((DDL / name).read_text()):
        db.command(command)


def import_collection(database, collection, path):
    client = docker.from_env()
    runner = client.containers.get(socket.gethostname())
    labels = [f"com.docker.compose.project={os.environ['COMPOSE_PROJECT_NAME']}", "com.docker.compose.service=mongo"]
    mongo, = client.containers.list(filters={"label": labels})
    workspace = next(mount["Source"] for mount in runner.attrs["Mounts"] if mount["Destination"] == WORKSPACE)
    client.containers.run(
        mongo.image.id,
        ["mongoimport", "--host", "mongo", "--db", database, "--collection", collection,
         "--file", str(Path(path).resolve()), "--stopOnError"],
        volumes={workspace: {"bind": WORKSPACE, "mode": "ro"}},
        network=next(iter(runner.attrs["NetworkSettings"]["Networks"])),
        nano_cpus=IMPORT_CPUS,
        remove=True,
        stderr=True,
    )


def logical_counts(db):
    counts = Counter()
    for collection, fields in COUNTS.items():
        group = {"_id": None} | {field: {"$sum": expression} for field, expression in fields.items()}
        row = next(db[collection].aggregate([{"$group": group}]), {})
        for field in fields:
            counts[field] += row.get(field, 0)
    return counts


def load(directory):
    expected = json.loads((directory / "manifest.json").read_text())["counts"]
    files = directory / "mongo"
    timings = {}
    start = time.perf_counter()
    transform(directory, files)
    timings["transform"] = time.perf_counter() - start
    with connect() as client:
        client.drop_database(DATABASE)
        db = client[DATABASE]
        start = time.perf_counter()
        run_script(db, "base/collections.json")
        for collection in COLLECTIONS:
            import_collection(DATABASE, collection, files / f"{collection}.json")
        timings["import"] = time.perf_counter() - start
        start = time.perf_counter()
        run_script(db, "base/indexes.json")
        timings["index"] = time.perf_counter() - start
        counts = logical_counts(db)
    links = counts.pop("shipLinks", 0)
    if counts != expected:
        raise ValueError(f"Logical counts {dict(counts)} differ from the manifest {expected}")
    if links != expected["shipment_"]:
        raise ValueError(f"shipLinks has {links} documents, expected {expected['shipment_']}")
    return {table: counts[table] for table in expected}, links, timings


def apply_index(db):
    run_script(db, "idx/indexes.json")
