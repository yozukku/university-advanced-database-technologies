import json
import os
import platform
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import docker
from docker.types import Mount

from bench.runner.state.containers import ENGINES, HELPER, project
from bench.runner.state.snapshot import SERVICE, root
from bench.scenarios.qhash import drivers, policy

LOCK = ".bench-lock"
HOST = {"macos": "ZTB_HOST_MACOS", "model": "ZTB_HOST_MODEL", "orbstack": "ZTB_HOST_ORBSTACK"}
REFLINK = "head -c 65536 /dev/zero > /probe/a && cp --reflink=always /probe/a /probe/b"
VERSIONS = {
    "pg": "show server_version",
    "mysql": "select version()",
    "neo4j": "CALL dbms.components() YIELD versions RETURN versions[0]",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def lock(directory, client):
    path = Path(directory) / LOCK
    if path.exists():
        owner = json.loads(path.read_text()).get("container")
        try:
            running = client.containers.get(owner).status == "running"
        except docker.errors.NotFound:
            running = False
        if running:
            raise SystemExit(f"A bench session in container {owner} holds {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"container": socket.gethostname(), "started": now()}) + "\n")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def reflink(client):
    volume = client.volumes.create(f"{project()}_reflink-probe")
    try:
        client.containers.run(HELPER, ["sh", "-euc", REFLINK], remove=True, network_mode="none", platform="linux/arm64",
                              mounts=[Mount("/probe", volume.name)])
        return True
    except docker.errors.ContainerError:
        return False
    finally:
        volume.remove(force=True)


def image(client, reference):
    try:
        found = client.images.get(reference)
    except docker.errors.ImageNotFound:
        return {"reference": reference}
    return {"reference": reference, "id": found.id, "repo_digests": found.attrs.get("RepoDigests", [])}


def settings(engine):
    directory = Path("docker/conf") / engine
    return {path.as_posix(): path.read_text() for path in sorted(directory.rglob("*")) if path.is_file()}


def describe(client, timeout):
    services = json.loads((root() / "compose.json").read_text())["services"]
    info = client.info()
    return {
        "recorded_at": now(),
        "host": {name: os.environ.get(variable, "unknown") for name, variable in HOST.items()},
        "docker": {"server_version": info.get("ServerVersion"), "operating_system": info.get("OperatingSystem"),
                   "kernel": info.get("KernelVersion"), "architecture": info.get("Architecture"), "cpus": info.get("NCPU"),
                   "memory_bytes": info.get("MemTotal"), "storage_driver": info.get("Driver")},
        "reflink": reflink(client),
        "runner": {"python": platform.python_version(), "drivers": drivers(),
                   "service": {key: services["runner"].get(key) for key in ("cpus", "platform")}},
        "policy": policy(timeout),
        "engines": {engine: {"image": image(client, services[engine]["image"]),
                             "service": {key: services[engine].get(key) for key in SERVICE},
                             "settings": settings(engine)} for engine in ENGINES},
    }


def version(session):
    if session.engine == "mongo":
        return session.client.admin.command("buildInfo")["version"]
    return str(session.fetch(VERSIONS[session.engine])[0][0])


def read(directory):
    target = Path(directory) / "env.json"
    return json.loads(target.read_text()) if target.exists() else {}


def versions(directory, size):
    engines = read(directory).get(size, {}).get("engines", {})
    return {engine: entry.get("version") for engine, entry in engines.items() if entry.get("version")}


def record(directory, size, values):
    target = Path(directory) / "env.json"
    found = read(directory)
    found[size] = values
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(found, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def record_version(directory, size, engine, value):
    found = read(directory)
    found[size]["engines"][engine]["version"] = value
    record(directory, size, found[size])
