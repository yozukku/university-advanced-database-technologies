import argparse
from pathlib import Path

from bench.gen.profiles import load_profile

from .loader import load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.size)
    counts, timings, timeout = load(args.data or profile.destination)
    for table, count in counts.items():
        print(f"{table}: {count:,}")
    phases = ", ".join(f"{phase} {seconds:.1f} s" for phase, seconds in timings.items())
    print(f"{profile.size}: {sum(counts.values()):,} rows loaded in {sum(timings.values()):.1f} s ({phases}), "
          f"statement_timeout {timeout}")


if __name__ == "__main__":
    main()
