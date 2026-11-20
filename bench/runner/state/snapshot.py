import json
import time
from hashlib import sha256
from pathlib import Path

import docker
import mysql.connector
from neo4j import GraphDatabase

from bench.check.verify.canonical import TABLES, kinds, read_schema
from bench.check.verify.engines import ENGINES as REBUILD
from bench.check.verify.engines import NEO4J_TABLES
from bench.check.verify.results import directory
from bench.gen.profiles import load_profile
from bench.load.mongo import loader as mongo_loader
from bench.load.mysql import loader as mysql_loader
from bench.load.neo4j import loader as neo4j_loader
from bench.load.pg import loader as pg_loader

from . import catalog
from .containers import (copy, engine_container, live_volume, others_running, project, snapshot_volume, stopped,
                         wait_ready)

INPUTS = ("bench/ddl/{}/base", "bench/ddl/{}/idx", "bench/transform/{}", "bench/load/{}", "docker/conf/{}")
SERVICE = ("image", "command", "environment", "cpus", "mem_limit")
BUILT_IMAGES = {"pg": Path("docker/postgres-postgis/Dockerfile")}
HASHED_SIZES = ("XS", "S")


def root():
    return Path("out/snapshots") / project()


def manifest_path(engine, size, config):
    return root() / size / f"{engine}-{config}.json"


def dataset(size):
    return json.loads((load_profile(size).destination / "manifest.json").read_text())


def inputs(engine, config):
    for pattern in INPUTS:
        if config == "base" and pattern.endswith("/idx"):
            continue
        for path in sorted(Path(pattern.format(engine)).rglob("*")):
            if path.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in path.parts):
                yield path.as_posix(), path.read_bytes()


def image(engine, service):
    if engine in BUILT_IMAGES:
        return BUILT_IMAGES[engine].read_bytes()
    reference, _, digest = service["image"].partition("@")
    if not digest:
        raise ValueError(f"{engine} image {reference} is not pinned by digest")
    return digest.encode()


def state_id(engine, size, config):
    service = json.loads((root() / "compose.json").read_text())["services"][engine]
    parts = [("dataset", dataset(size)["dataset_sha256"].encode()), *inputs(engine, config),
             ("service", json.dumps({key: service.get(key) for key in SERVICE}, sort_keys=True).encode()),
             ("image", image(engine, service))]
    digest = sha256()
    for name, data in parts:
        digest.update(f"{name}\0{len(data)}\0".encode())
        digest.update(data)
    return digest.hexdigest()


def counts(engine):
    if engine == "pg":
        with pg_loader.connect() as conn:
            return {table: conn.execute(f"select count(*) from {table}").fetchone()[0] for table in TABLES}
    if engine == "mysql":
        with mysql.connector.connect(**mysql_loader.SERVER, database=mysql_loader.DATABASE) as conn, conn.cursor() as cursor:
            return {table: mysql_loader.fetch(cursor, f"select count(*) from {table}")[0][0] for table in TABLES}
    if engine == "mongo":
        with mongo_loader.connect() as client:
            found = mongo_loader.logical_counts(client[mongo_loader.DATABASE])
        return {table: found[table] for table in TABLES}
    with (GraphDatabase.driver(neo4j_loader.URI, auth=neo4j_loader.AUTH, notifications_min_severity="OFF") as driver,
          driver.session(database="neo4j") as session):
        return {table: session.run(f"MATCH (n:{label}) RETURN count(n)").single()[0]
                for table, (label, _) in NEO4J_TABLES.items()}


def fingerprint(engine, size):
    found = {"counts": counts(engine)}
    if size in HASHED_SIZES:
        schema = read_schema(load_profile(size).destination)
        digests, _, _ = REBUILD[engine](schema, kinds(schema), [])
        found["hashes"] = {table: digests[table]["hash"] if table in digests else None for table in TABLES}
    return found


def take(client, container, engine, size, config, found):
    path = manifest_path(engine, size, config)
    path.unlink(missing_ok=True)
    manifest = {"state_id": state_id(engine, size, config), "engine": engine, "size": size, "config": config,
                "volume": snapshot_volume(engine, size, config), "fingerprint": found}
    start = time.perf_counter()
    stopped(container)
    copy(client, live_volume(container), manifest["volume"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"{engine} {size} {config}: snapshot {manifest['volume']} in {time.perf_counter() - start:.1f} s")


def index_apply(engine):
    if engine == "pg":
        with pg_loader.connect() as conn:
            built, statistics = pg_loader.apply_index(conn)
            return built, statistics, {"statement_timeout": pg_loader.setting(conn, "statement_timeout")}
    if engine == "mysql":
        with mysql.connector.connect(**mysql_loader.SERVER, database=mysql_loader.DATABASE) as conn, conn.cursor() as cursor:
            return *mysql_loader.apply_index(cursor), {}
    if engine == "mongo":
        with mongo_loader.connect() as client:
            return *mongo_loader.apply_index(client[mongo_loader.DATABASE]), {}
    with (GraphDatabase.driver(neo4j_loader.URI, auth=neo4j_loader.AUTH, notifications_min_severity="OFF") as driver,
          driver.session(database="neo4j") as session):
        return *neo4j_loader.apply_index(session), {}


def record_build(size, engine, values):
    target = directory(size) / "index_build.json"
    results = json.loads(target.read_text()) if target.exists() else {}
    results.setdefault(size, {})[engine] = values
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def require(problems, context):
    if problems:
        raise SystemExit(f"{context}:\n  " + "\n  ".join(problems))


def snapshots(engine, size):
    client = docker.from_env()
    container = engine_container(client, engine)
    base_print = fingerprint(engine, size)
    expected_counts = dataset(size)["counts"]
    require([f"{table}: {count:,} rows, dataset {expected_counts[table]:,}" for table, count in base_print["counts"].items()
             if count != expected_counts[table]], f"{engine} does not hold the {size} dataset")
    base = catalog.read(engine)
    require(catalog.compare(engine, base, catalog.expected(engine, "base")), f"{engine} BASE catalog differs from the BASE map")
    take(client, container, engine, size, "base", base_print)

    container.start()
    wait_ready(container)
    built, statistics, session = index_apply(engine)
    idx = catalog.read(engine)
    added, problems = catalog.added(engine, base, idx)
    require(problems + catalog.compare(engine, added, catalog.expected(engine, "idx")),
            f"{engine} IDX − BASE differs from the IDX objects")
    idx_print = fingerprint(engine, size)
    require(["data changed while the IDX indexes were built"] if idx_print != base_print else [], engine)
    take(client, container, engine, size, "idx", idx_print)

    indexes = {name: {"scope": scope, "kind": kind, "seconds": round(built[name], 3), "bytes": entry.get("bytes")}
               for (scope, name, kind), entry in added.items()}
    record_build(size, engine, {"base": catalog.listing(base), "idx": catalog.listing(idx), "indexes": indexes,
                                "statistics": {step: round(seconds, 3) for step, seconds in statistics.items()}, **session})
    for name, index in sorted(indexes.items()):
        print(f"{engine} {name}: built in {index['seconds']:.2f} s, {index['bytes'] or 0:,} bytes")


def restore(engine, size, config):
    client = docker.from_env()
    manifest = json.loads(manifest_path(engine, size, config).read_text())
    current = state_id(engine, size, config)
    if manifest["state_id"] != current:
        raise SystemExit(f"{engine} {size} {config}: snapshot state {manifest['state_id'][:12]} is stale, "
                         f"current {current[:12]}; rebuild it with make snapshots")
    if running := others_running(client, engine):
        raise SystemExit(f"Another database is running: {', '.join(running)}")
    container = engine_container(client, engine)
    start = time.perf_counter()
    stopped(container, kill=True)
    copy(client, manifest["volume"], live_volume(container))
    container.start()
    wait_ready(container)
    print(f"{engine} {size} {config}: restored from {manifest['volume']} and ready in {time.perf_counter() - start:.1f} s")


def check(engine, size, config):
    manifest = json.loads(manifest_path(engine, size, config).read_text())
    problems = [] if manifest["state_id"] == state_id(engine, size, config) else ["the snapshot state_id is stale"]
    found = fingerprint(engine, size)
    if found != manifest["fingerprint"]:
        problems.append(f"fingerprint {found} differs from the snapshot {manifest['fingerprint']}")
    wanted = catalog.expected(engine, "base") | (catalog.expected(engine, "idx") if config == "idx" else {})
    problems += catalog.compare(engine, catalog.read(engine), wanted)
    require(problems, f"{engine} {size} {config} differs from its snapshot")
    hashed = "row counts and table hashes" if "hashes" in found else "row counts"
    print(f"{engine} {size} {config}: state {manifest['state_id'][:12]}, {hashed} and catalog equal the snapshot")
