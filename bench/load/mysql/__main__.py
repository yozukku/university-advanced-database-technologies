import argparse
from pathlib import Path

from bench.check.verify.results import record_load
from bench.gen.profiles import load_profile

from .loader import load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.size)
    counts, timings = load(args.data or profile.destination)
    for table, count in counts.items():
        print(f"{table}: {count:,}")
    record_load(profile.size, "mysql", timings)
    phases = ", ".join(f"{phase} {seconds:.1f} s" for phase, seconds in timings.items())
    print(f"{profile.size}: {sum(counts.values()):,} rows loaded in {sum(timings.values()):.1f} s ({phases}), "
          f"innodb_table_stats {len(counts)}/{len(counts)}")


if __name__ == "__main__":
    main()
