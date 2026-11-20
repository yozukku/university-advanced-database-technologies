import os
import shutil
import socket
import time
from pathlib import Path

import docker
from neo4j import GraphDatabase

from bench.transform.neo4j.transform import write

DDL = Path("bench/ddl/neo4j")
URI = "bolt://neo4j:7687"
AUTH = ("neo4j", "benchmark")
IMPORT = [
    "neo4j-admin", "database", "import", "full", "neo4j", "--overwrite-destination=true", "--id-type=integer",
    "--bad-tolerance=0", "--max-off-heap-memory=4G",
]
STORE = ("/data/databases/neo4j", "/data/transactions/neo4j")
READY_SECONDS = 600


def engine(client):
    project = os.environ["COMPOSE_PROJECT_NAME"]
    labels = [f"com.docker.compose.project={project}", "com.docker.compose.service=neo4j"]
    [container] = client.containers.list(all=True, filters={"label": labels})
    return container


def host_path(client, path):
    path = path.resolve()
    for mount in client.containers.get(socket.gethostname()).attrs["Mounts"]:
        if path.is_relative_to(mount["Destination"]):
            return str(Path(mount["Source"]) / path.relative_to(mount["Destination"]))
    raise RuntimeError(f"{path} is not on a mount shared with the Docker host")


def wait_ready(container):
    deadline = time.monotonic() + READY_SECONDS
    while True:
        container.reload()
        state = container.attrs["State"]
        if state["Health"]["Status"] == "healthy":
            return
        if state["Status"] != "running" or time.monotonic() > deadline:
            raise RuntimeError(f"neo4j is {state['Status']} and {state['Health']['Status']}")
        time.sleep(1)


def import_store(client, staging, nodes, relationships):
    container = engine(client)
    data = next(mount["Name"] for mount in container.attrs["Mounts"] if mount["Destination"] == "/data")
    files = [f"--nodes={labels}=/import/{path.name}" for labels, path in nodes]
    files += [f"--relationships={kind}=/import/{path.name}" for kind, path in relationships]
    volumes = {data: {"bind": "/data", "mode": "rw"}}
    container.stop(timeout=120)
    try:
        client.containers.run(
            container.image.id, IMPORT + files, remove=True,
            volumes=volumes | {host_path(client, staging): {"bind": "/import", "mode": "ro"}},
            nano_cpus=container.attrs["HostConfig"]["NanoCpus"], mem_limit=container.attrs["HostConfig"]["Memory"],
        )
    except docker.errors.ContainerError:
        client.containers.run(container.image.id, ["rm", "-rf", *STORE], remove=True, volumes=volumes)
        raise
    finally:
        container.start()
    wait_ready(container)


def run_script(session, name):
    for statement in (DDL / name).read_text().split(";"):
        if statement.strip():
            session.run(statement).consume()


def catalog_counts(session):
    counts = {}
    for label in session.run("call db.labels() yield label return label").value():
        counts[label] = session.run(f"match (n:`{label}`) return count(n)").single()[0]
    for kind in session.run("call db.relationshipTypes() yield relationshipType return relationshipType").value():
        counts[kind] = session.run(f"match ()-[r:`{kind}`]->() return count(r)").single()[0]
    return counts


def load(directory):
    staging = directory / "neo4j"
    timings = {}
    start = time.perf_counter()
    nodes, relationships, expected = write(directory, staging)
    timings["transform"] = time.perf_counter() - start
    start = time.perf_counter()
    import_store(docker.from_env(), staging, nodes, relationships)
    timings["import"] = time.perf_counter() - start
    shutil.rmtree(staging)
    with GraphDatabase.driver(URI, auth=AUTH) as driver, driver.session(database="neo4j") as session:
        counts = catalog_counts(session)
        differences = {name: (expected.get(name, 0), counts.get(name, 0)) for name in expected.keys() | counts.keys()
                       if expected.get(name, 0) != counts.get(name, 0)}
        if differences:
            raise ValueError(f"Neo4j counts differ from canonical (expected, actual): {differences}")
        start = time.perf_counter()
        run_script(session, "base/constraints.cypher")
        run_script(session, "base/indexes.cypher")
        timings["base"] = time.perf_counter() - start
    return {name: counts.get(name, 0) for name in expected}, timings


def apply_index(session):
    run_script(session, "idx/indexes.cypher")
