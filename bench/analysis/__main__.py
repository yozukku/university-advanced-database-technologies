import argparse
import os
import sys
from pathlib import Path

from bench.check.verify.results import root
from bench.runner.matrix import CONFIGS, Bench
from bench.scenarios.qhash import TIMEOUT_SECONDS

from . import h1, qa


def check(size, timeout):
    bench = Bench(size, timeout=timeout)
    cells = []
    for engine in bench.engines:
        for config in CONFIGS:
            for scenario in bench.group(engine, config):
                key = bench.key(scenario, engine, config)
                cells.append((scenario, key, bench.store.cell(key)))
    return qa.write(root(size) / "qa.json", size, qa.check(cells))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("qa", "h1"))
    parser.add_argument("--size", choices=("XS", "S", "M", "L"))
    parser.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS)
    parser.add_argument("--results", type=Path, default=Path(os.environ.get("RESULTS_DIR") or "results"))
    args = parser.parse_args()
    if args.command == "qa":
        if not args.size:
            parser.error("qa needs --size")
        sys.exit(check(args.size, args.timeout))
    sys.exit(h1.main(args.results))


if __name__ == "__main__":
    main()
