import argparse
import json
import sys
import time
from pathlib import Path

from bench.gen.profiles import load_profile

from .canonical import DERIVED, TABLES, canonical_rows, digest, kinds, read_schema
from .engines import ENGINES
from .results import read, record, write

ENGINE_DERIVED = {
    "pg": (),
    "mysql": ("changes_new_",),
    "mongo": ("reservations.lockermatId", "shipment.lockermatIds", "shipLinks"),
    "neo4j": ("SHIPS_TO",),
}
EMPTY = {"rows": 0, "hash": "0" * 64}
DISTANCE_KM = (250, 253)
PROBLEMS = 20


def inspect(size, directory, engine):
    schema = read_schema(directory)
    problems = []
    start = time.perf_counter()
    digests, distance, disk = ENGINES[engine](schema, kinds(schema), problems)
    seconds = time.perf_counter() - start
    record(size, engine, {
        "tables": {table: digests.get(table, EMPTY) for table in TABLES},
        "derived": {name: digests.get(name, EMPTY) for name in ENGINE_DERIVED[engine]},
        "problems": problems[:PROBLEMS],
        "problem_count": len(problems),
        "distance_km": round(distance / 1000, 3),
        "disk_bytes": int(disk),
        "verify_seconds": round(seconds, 1),
    })
    rows = sum(digests.get(table, EMPTY)["rows"] for table in TABLES)
    print(f"{engine}: {rows:,} rows of {len(TABLES)} tables rebuilt in {seconds:.1f} s, {len(problems)} problems")


def describe(digested):
    return f"{digested['rows']:,} rows, hash {digested['hash'][:12]}" if digested else "not verified"


def check(label, actual, expected, failures):
    if actual == expected:
        return actual["hash"][:12]
    failures.append(f"{label}: {describe(actual)}, canonical {describe(expected)}")
    return "≠" + actual["hash"][:11] if actual else "missing"


def line(label, rows, cells):
    return (f"{label:<26}{rows:>10}  " + "".join(f"{cell:<14}" for cell in cells)).rstrip()


def figures(engines, key, scale, digits):
    values = [engines.get(engine, {}).get(key) for engine in ENGINES]
    return ["—" if value is None else f"{value / scale:,.{digits}f}" for value in values]


def compare(size, directory):
    schema = read_schema(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    canonical = digest(canonical_rows(directory, schema), kinds(schema))
    results = read(size)
    engines = results.get("engines", {})
    failures = []
    if {table: canonical.get(table, EMPTY)["rows"] for table in TABLES} != manifest["counts"]:
        failures.append("canonical Parquet rows differ from the manifest")

    lines = [f"{size}: {len(TABLES)} tables × {len(ENGINES)} engines, dataset {manifest['dataset_sha256'][:12]}",
             line("table", "rows", ENGINES)]
    for table in TABLES:
        expected = canonical.get(table, EMPTY)
        cells = [check(f"{engine} {table}", engines.get(engine, {}).get("tables", {}).get(table), expected, failures)
                 for engine in ENGINES]
        lines.append(line(table, f"{expected['rows']:,}", cells))
    lines.append("derived data")
    for name in DERIVED:
        expected = canonical.get(name, EMPTY)
        cells = [check(f"{engine} {name}", engines.get(engine, {}).get("derived", {}).get(name), expected, failures)
                 if name in ENGINE_DERIVED[engine] else "" for engine in ENGINES]
        lines.append(line(name, f"{expected['rows']:,}", cells))
    lines.append(line("distance [km]", "", figures(engines, "distance_km", 1, 3)))
    lines.append(line("load [s]", "", figures(engines, "load_seconds", 1, 1)))
    lines.append(line("disk [MB]", "", figures(engines, "disk_bytes", 1_000_000, 1)))

    for engine in ENGINES:
        distance = engines.get(engine, {}).get("distance_km")
        if distance is None or not DISTANCE_KM[0] <= distance <= DISTANCE_KM[1]:
            failures.append(f"{engine}: distance {distance} km is outside {DISTANCE_KM[0]}–{DISTANCE_KM[1]} km")
        if count := engines.get(engine, {}).get("problem_count"):
            failures.append(f"{engine}: {count} problems")
            failures.extend(f"  {problem}" for problem in engines[engine]["problems"])

    results.update({
        "size": size,
        "dataset_sha256": manifest["dataset_sha256"],
        "canonical": {
            "tables": {table: canonical.get(table, EMPTY) for table in TABLES},
            "derived": {name: canonical.get(name, EMPTY) for name in DERIVED},
        },
        "equal": not failures,
    })
    write(size, results)
    print("\n".join(lines))
    if failures:
        print("FAILED:", *failures, sep="\n")
        return False
    print(f"OK: {len(TABLES)} tables and their derived data equal the canonical Parquet in {len(ENGINES)} engines, "
          f"distances {DISTANCE_KM[0]}–{DISTANCE_KM[1]} km")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--engine", choices=tuple(ENGINES))
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.size)
    directory = args.data or profile.destination
    if args.engine:
        inspect(profile.size, directory, args.engine)
    elif not compare(profile.size, directory):
        sys.exit(1)


if __name__ == "__main__":
    main()
