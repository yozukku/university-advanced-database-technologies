import os
import sys

import docker

ENGINES = {"pg", "mysql", "mongo", "neo4j"}


def main():
    project = os.environ["COMPOSE_PROJECT_NAME"]
    client = docker.from_env()
    containers = client.containers.list(
        filters={"label": [f"com.docker.compose.project={project}", "com.docker.compose.oneoff=False"]})
    engines = sorted(container.name for container in containers
                     if container.labels.get("com.docker.compose.service") in ENGINES)
    if len(engines) > 1:
        sys.exit(f"More than one database is running for {project}: {', '.join(engines)}")

    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])
    for name in engines:
        print(name)


if __name__ == "__main__":
    main()
