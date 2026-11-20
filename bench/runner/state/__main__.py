import argparse

from .containers import ENGINES
from .snapshot import check, restore, snapshots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("snapshots", "restore", "check"))
    parser.add_argument("--engine", choices=ENGINES, required=True)
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--config", choices=("base", "idx"))
    args = parser.parse_args()
    if args.command == "snapshots":
        snapshots(args.engine, args.size)
    elif args.config is None:
        parser.error(f"{args.command} needs --config base or idx")
    elif args.command == "restore":
        restore(args.engine, args.size, args.config)
    else:
        check(args.engine, args.size, args.config)


if __name__ == "__main__":
    main()
