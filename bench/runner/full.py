import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import tomllib
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache, partial
from hashlib import sha256
from pathlib import Path
from typing import Callable

import docker

from bench.check.verify.results import root
from bench.gen.profiles import load_profile
from bench.scenarios.registry import ENGINES

from .explain import directory as plans
from .explain import wanted
from .matrix import CONFIGS, Bench
from .state import snapshot as state
from .state.containers import engine_container, others_running, project, stopped, wait_ready

STEPS = ("data", "validate", "load", "verify", "snapshots", "bench", "explain", "qa", "h1", "charts", "report")
PLANNED = ("XS", "S", "L")
LIBRARIES = ("faker", "numpy", "pyarrow")
JOURNAL = "full-run.jsonl"
WORKSPACE = "/workspace"


class Interrupted(BaseException):
    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


@dataclass
class Step:
    name: str
    engine: str | None
    run: Callable[[], int]
    key: Callable[[], str | None] = lambda: None
    done: Callable[[str | None], bool] = lambda key: False
    marker: Path | None = None


def interrupt(signum, frame):
    raise Interrupted(signum)


def digest(*parts):
    found = sha256()
    for name, data in parts:
        found.update(f"{name}\0{len(data)}\0".encode())
        found.update(data)
    return found.hexdigest()


def files(*paths):
    for path in map(Path, paths):
        for found in sorted([path] if path.is_file() else path.rglob("*")):
            if found.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in found.parts):
                yield found.as_posix(), found.read_bytes()


def libraries():
    packages = tomllib.loads(Path("uv.lock").read_text())["package"]
    return json.dumps({package["name"]: package["version"] for package in packages if package["name"] in LIBRARIES},
                      sort_keys=True).encode()


def data_key(size):
    return digest(("size", size.encode()), ("libraries", libraries()), *files("bench/gen", "profiles.yaml"))


def validate_key(size):
    return digest(("dataset", state.dataset(size)["dataset_sha256"].encode()), *files("bench/scenarios/ops.yaml", "bench/check"))


def verify_key(size):
    return digest(*((engine, state.state_id(engine, size, "base").encode()) for engine in ENGINES))


def recorded(marker, key):
    return marker.exists() and marker.read_text() == key


def current(engine, size, config):
    path = state.manifest_path(engine, size, config)
    return path.exists() and json.loads(path.read_text())["state_id"] == state.state_id(engine, size, config)


def invoke(*argv):
    child = subprocess.Popen(argv)
    try:
        return child.wait()
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGINT)
            child.wait()


def module(*argv):
    return invoke(sys.executable, "-m", *argv)


@contextmanager
def engine_up(engine):
    client = docker.from_env()
    if running := others_running(client, engine):
        raise RuntimeError(f"Another database is running: {', '.join(running)}")
    container = engine_container(client, engine)
    container.start()
    wait_ready(container)
    try:
        yield
    finally:
        stopped(container)


def served(engine, *argv):
    with engine_up(engine):
        return module(*argv)


def snapshot(engine, size):
    if current(engine, size, "base"):
        if code := module("bench.runner.state", "restore", "--engine", engine, "--size", size, "--config", "base"):
            return code
    return served(engine, "bench.runner.state", "snapshots", "--engine", engine, "--size", size)


def report_image(*argv):
    client = docker.from_env()
    runner = client.containers.get(socket.gethostname())
    workspace = next(mount["Source"] for mount in runner.attrs["Mounts"] if mount["Destination"] == WORKSPACE)
    container = client.containers.run(f"{project()}-report".lower(), ["python", "-m", *argv], detach=True,
                                      working_dir=WORKSPACE, network_mode="none",
                                      volumes={workspace: {"bind": WORKSPACE, "mode": "rw"}})
    try:
        for chunk in container.logs(stream=True, follow=True):
            sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
        return container.wait()["StatusCode"]
    finally:
        container.remove(force=True)


@cache
def matrix(size):
    return Bench(size)


def snapshotted(size, engine):
    return current(engine, size, "base") and current(engine, size, "idx")


def measured(size, engine):
    bench = matrix(size)
    return not any(bench.pending(scenario, engine, config)[0] for config in CONFIGS for scenario in bench.group(engine, config))


def planned(size, engine):
    bench = matrix(size)
    return all((plans(size) / name).exists() for config in CONFIGS for name in wanted(bench, engine, config))


def steps(size):
    markers = Path("out/state") / project() / size

    def marked(name, engine, run, key, ready=lambda: True):
        marker = markers / f"{name}-{engine or 'all'}.key"
        return Step(name, engine, run, key, lambda value: recorded(marker, value) and ready(), marker)

    def kept(name, engine, run, done):
        return Step(name, engine, run, partial(state.state_id, engine, size, "idx"), lambda key: done(size, engine))

    def base(engine):
        return partial(state.state_id, engine, size, "base")

    found = [
        marked("data", None, partial(module, "bench.gen", "--size", size), partial(data_key, size),
               lambda: (load_profile(size).destination / "manifest.json").exists()),
        marked("validate", None, partial(module, "bench.check", "--size", size), partial(validate_key, size)),
    ]
    found += [marked("load", engine, partial(served, engine, f"bench.load.{engine}", "--size", size), base(engine))
              for engine in ENGINES]
    found += [marked("verify", engine, partial(served, engine, "bench.check.verify", "--size", size, "--engine", engine),
                     base(engine)) for engine in ENGINES]
    found.append(marked("verify", None, partial(module, "bench.check.verify", "--size", size), partial(verify_key, size)))
    found += [kept("snapshots", engine, partial(snapshot, engine, size), snapshotted) for engine in ENGINES]
    found += [kept("bench", engine, partial(module, "bench.runner", "run", "--size", size, "--engine", engine), measured)
              for engine in ENGINES]
    if size in PLANNED:
        found += [kept("explain", engine, partial(module, "bench.runner", "explain", "--size", size, "--engine", engine),
                       planned) for engine in ENGINES]
    found.append(Step("qa", None, partial(module, "bench.analysis", "qa", "--size", size)))
    return found


def tail(directory, out):
    return [Step("h1", None, partial(module, "bench.analysis", "h1", "--results", str(directory))),
            Step("charts", None, partial(report_image, "bench.analysis.charts", "--results", str(directory))),
            Step("report", None, partial(report_image, "bench.report", "--results", str(directory), "--out", str(out)))]


def append(journal, line):
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a") as target:
        target.write(json.dumps(line, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())


def execute(step, size, journal):
    label = " ".join(filter(None, (size, step.name, step.engine)))
    try:
        key = step.key()
        if step.done(key):
            print(f"full: {label}: done")
            return 0
    except Exception:
        traceback.print_exc()
        print(f"full: {label}: inputs could not be read")
        return 1
    print(f"full: {label}")
    start = time.monotonic()
    code = 1
    try:
        code = step.run()
    except Interrupted as error:
        code = 128 + error.signum
        raise
    except Exception:
        traceback.print_exc()
    finally:
        seconds = time.monotonic() - start
        append(journal, {"size": size, "step": step.name, "engine": step.engine, "state_id": key,
                         "seconds": round(seconds, 3), "exit": code})
    if code == 0 and step.marker:
        step.marker.parent.mkdir(parents=True, exist_ok=True)
        step.marker.write_text(key)
    print(f"full: {label}: exit {code} in {seconds:.1f} s")
    return code


def groups(sizes):
    found = {}
    for size in sizes:
        found.setdefault(root(size), set()).add(size)
    return [(directory, Path("out/xs") if members == {"XS"} else Path("out")) for directory, members in found.items()]


def run(sizes, until=None, plan=steps, finish=tail):
    last = STEPS.index(until or STEPS[-1])
    failures = []
    for size in sizes:
        broken = False
        for step in plan(size):
            if STEPS.index(step.name) > last or (broken and step.name != "qa"):
                continue
            if code := execute(step, size, root(size) / JOURNAL):
                broken = True
                failures.append((size, step, code))
    for directory, out in groups(sizes):
        for step in finish(directory, out):
            if STEPS.index(step.name) <= last and (code := execute(step, None, directory / JOURNAL)):
                failures.append(("-", step, code))
    if failures:
        size, step, code = failures[0]
        print(f"full: first failed step: {size} {step.name}{' ' + step.engine if step.engine else ''} (exit {code})")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--until", choices=STEPS)
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        code = run(args.sizes, args.until)
    except Interrupted as error:
        print(f"full: interrupted by signal {error.signum}")
        code = 128 + error.signum
    sys.exit(code)


if __name__ == "__main__":
    main()
