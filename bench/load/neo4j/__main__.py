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
    counts, timings = load(args.data or profile.destination)
    for name, count in counts.items():
        print(f"{name}: {count:,}")
    phases = ", ".join(f"{phase} {seconds:.1f} s" for phase, seconds in timings.items())
    print(f"{profile.size}: {len(counts)} labels and relationship types equal canonical, "
          f"loaded in {sum(timings.values()):.1f} s ({phases})")


if __name__ == "__main__":
    main()
