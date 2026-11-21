import argparse
import signal
import sys

import docker

from bench.check.verify.results import root
from bench.scenarios.qhash import TIMEOUT_SECONDS
from bench.scenarios.registry import ENGINES

from . import environment, explain
from .matrix import Bench
from .store import Store


def terminate(*_):
    sys.exit(143)


def run(bench):
    directory = root(bench.size)
    with environment.lock(directory, bench.client):
        known = environment.versions(directory, bench.size)
        env = environment.describe(bench.client, bench.timeout)
        for engine, entry in env["engines"].items():
            entry["version"] = known.get(engine)
        environment.record(directory, bench.size, env)
        bench.run()
    print_status(bench)


def plans(bench):
    with environment.lock(root(bench.size), bench.client):
        failed = explain.run(bench)
    print(f"{bench.size}: {explain.directory(bench.size)}")
    if failed:
        raise SystemExit("Plans not captured:\n  " + "\n  ".join(failed))


def forget(args, parser):
    if len(args.engine or ()) != 1 or len(args.scenario or ()) != 1 or not args.reason:
        parser.error("forget needs one --engine, one --scenario and --reason")
    directory = root(args.size)
    with environment.lock(directory, docker.from_env()):
        removed = Store(directory).forget(args.engine[0], args.size, args.scenario[0])
        with (directory / "notes.md").open("a") as notes:
            notes.write(f"- {environment.now()} make forget ENGINE={args.engine[0]} SIZE={args.size} "
                        f"SCENARIO={args.scenario[0]}: {removed} lines removed; {args.reason}\n")
    print(f"{args.engine[0]} {args.size} {args.scenario[0]}: {removed} lines removed from {directory / 'runs.jsonl'}")


def print_status(bench):
    print(f"{bench.size}: {bench.store.path}")
    print(f"{'engine':<7}{'config':<7}{'cells':>6}{'done':>6}{'timeout':>8}{'error':>6}  outstanding")
    for engine, config, cells, done, timeouts, errors, outstanding in bench.status():
        print(f"{engine:<7}{config:<7}{cells:>6}{done:>6}{timeouts:>8}{errors:>6}  {outstanding}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "status", "forget", "explain"))
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--engine", action="append", choices=ENGINES)
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS)
    parser.add_argument("--reason")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    signal.signal(signal.SIGTERM, terminate)
    if args.command == "forget":
        forget(args, parser)
        return
    if args.command == "explain" and args.size == "M":
        parser.error("plans are captured at XS, S and L, not at M")
    bench = Bench(args.size, tuple(args.engine or ENGINES), set(args.scenario or ()), args.timeout)
    if args.command == "run":
        run(bench)
    elif args.command == "explain":
        plans(bench)
    else:
        print_status(bench)


if __name__ == "__main__":
    main()
