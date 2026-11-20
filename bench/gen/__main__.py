import argparse
from pathlib import Path

import pyarrow.parquet as pq

from .plan import make_plan
from .profiles import load_profile
from .static import static_tables


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.size)
    output = args.output or profile.destination
    output.mkdir(parents=True, exist_ok=True)

    plan = make_plan(profile)
    for name, table in static_tables(profile, plan):
        pq.write_table(table, output / f"{name}.parquet", compression="zstd")
        print(f"{name}: {table.num_rows:,}")


if __name__ == "__main__":
    main()
