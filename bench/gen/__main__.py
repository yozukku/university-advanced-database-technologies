import argparse
from pathlib import Path

from .dataset import write_dataset
from .profiles import load_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.size)
    _, tables = write_dataset(profile, args.output or profile.destination)
    for name, table in tables.items():
        print(f"{name}: {table.num_rows:,}")


if __name__ == "__main__":
    main()
