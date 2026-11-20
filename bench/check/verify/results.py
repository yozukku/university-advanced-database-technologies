import json
from pathlib import Path


def path(size):
    return (Path("out/xs/results") if size == "XS" else Path("results")) / "load" / f"{size}.json"


def read(size):
    source = path(size)
    return json.loads(source.read_text()) if source.exists() else {}


def write(size, results):
    target = path(size)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def record(size, engine, values):
    results = read(size)
    results.setdefault("engines", {}).setdefault(engine, {}).update(values)
    write(size, results)


def record_load(size, engine, timings):
    record(size, engine, {
        "load_seconds": round(sum(timings.values()), 1),
        "load_phases": {phase: round(seconds, 1) for phase, seconds in timings.items()},
    })
