import argparse
import json
from pathlib import Path

from bench.gen.dataset import make_manifest
from bench.gen.plan import make_plan
from bench.gen.profiles import load_profile

from .audit import check_audit
from .ledger import TABLES, check_ledger
from .parquet import connect
from .scenarios import check_scenarios


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--ops", type=Path, default=Path("bench/scenarios/ops.yaml"))
    args = parser.parse_args()

    profile = load_profile(args.size)
    directory = args.data or profile.destination
    plan = make_plan(profile)
    expected = json.loads((directory / "manifest.json").read_text())
    present = {path.stem for path in directory.glob("*.parquet")}
    if present != set(plan.counts):
        raise ValueError(f"{profile.size}: canonical table files differ: {sorted(present ^ set(plan.counts))}")
    with connect(directory, (*TABLES, "audit_event_")) as db:
        db.execute("set timezone = 'UTC'")
        check_ledger(db, profile, plan)
        check_audit(db, plan)
        check_scenarios(db, profile, args.ops)

    actual = make_manifest(directory, profile, plan.counts)
    if expected != actual:
        raise ValueError(f"{profile.size}: manifest and canonical Parquet hashes differ")
    print(f"{profile.size}: {sum(plan.counts.values()):,} rows, dataset SHA-256 {actual['dataset_sha256']}")


if __name__ == "__main__":
    main()
