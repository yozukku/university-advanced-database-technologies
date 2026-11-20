import os
import time

from docker.types import Mount

ENGINES = ("pg", "mysql", "mongo", "neo4j")
HELPER = "debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc"
COPY = "find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; cp -a --reflink=auto /source/. /target/"
READY_SECONDS = 600


def project():
    return os.environ["COMPOSE_PROJECT_NAME"]


def services(client, **filters):
    labels = [f"com.docker.compose.project={project()}", "com.docker.compose.oneoff=False"]
    return client.containers.list(filters={"label": labels}, **filters)


def engine_container(client, engine):
    found = [container for container in services(client, all=True)
             if container.labels.get("com.docker.compose.service") == engine]
    if len(found) != 1:
        raise RuntimeError(f"Expected one {engine} container in {project()}, found {len(found)}; run make up ENGINE={engine}")
    return found[0]


def others_running(client, engine):
    return sorted(container.name for container in services(client)
                  if container.labels.get("com.docker.compose.service") in set(ENGINES) - {engine})


def live_volume(container):
    [name] = [mount["Name"] for mount in container.attrs["Mounts"] if mount["Type"] == "volume"]
    return name


def snapshot_volume(engine, size, config):
    return f"{project()}_{engine}-snapshot-{size}-{config}".lower()


def stopped(container, kill=False):
    container.reload()
    if container.status == "running":
        if kill:
            container.kill()
        else:
            container.stop(timeout=120)
        container.wait(condition="not-running")


def copy(client, source, target):
    client.volumes.get(source)
    client.volumes.create(target)
    client.containers.run(
        HELPER, ["sh", "-euc", COPY], remove=True, network_mode="none", platform="linux/arm64",
        mounts=[Mount("/source", source, read_only=True), Mount("/target", target)],
    )


def wait_ready(container):
    deadline = time.monotonic() + READY_SECONDS
    while True:
        container.reload()
        state = container.attrs["State"]
        health = state.get("Health", {}).get("Status")
        if health == "healthy":
            return
        if state["Status"] != "running" or time.monotonic() > deadline:
            raise RuntimeError(f"{container.name} is {state['Status']} and {health}")
        time.sleep(0.5)
