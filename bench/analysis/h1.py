import csv
import json
import re

from bench.scenarios.catalogue import H1, INDEXES
from bench.scenarios.registry import ENGINES, JSON_ENGINES, position

SIZES = ("XS", "S", "M", "L")
VERDICT_SIZE = "L"
READS = "H1-S"
CONFIRMED = "potwierdzona"
REJECTED = "obalona"
NAME = re.compile(r"\w+")


def engines(scenario):
    return JSON_ENGINES if scenario.startswith("J") else ENGINES


def served(plan, scenario, engine):
    return {item["name"] for row in plan.values() if scenario in row["serves"] for item in row["engines"][engine]}


def plans(directory):
    path = directory / "explain_summary.csv"
    if not path.exists():
        return {}
    with path.open(newline="") as source:
        return {row["file"]: set(NAME.findall(row["index"])) for row in csv.DictReader(source)}


def plan_key(size, cell):
    return f"{cell['scenario']}-{cell['engine']}-{cell['config']}-{size}-{cell['qhash'][:12]}-{cell['state_id'][:12]}.json"


def evaluate(kind, size, base, idx, names, found):
    entry = {"set": kind, "size": size, "base_mean": base and base.get("mean"), "idx_mean": idx and idx.get("mean"),
             "base_censored": bool(base) and base["state"] == "censored", "ratio": None, "direction": None,
             "plan": None, "holds": None, "complete": False}
    if not idx or idx["state"] != "complete" or not base or base["state"] == "incomplete":
        return entry
    if entry["base_censored"]:
        entry |= {"direction": "faster", "base_seconds": base["seconds"]}
    else:
        entry |= {"ratio": idx["mean"] / base["mean"],
                  "direction": "faster" if idx["mean"] < base["mean"] else "slower" if idx["mean"] > base["mean"] else "equal"}
    if kind != READS:
        return entry | {"holds": entry["direction"] == "slower", "complete": True}
    used = found.get(plan_key(size, idx))
    if used is None:
        return entry
    entry["plan"] = bool(used & names)
    return entry | {"holds": entry["direction"] == "faster" and entry["plan"], "complete": plan_key(size, base) in found}


def cells(qa, found, plan):
    entries = []
    for size in SIZES:
        if size not in qa:
            continue
        index = {(cell["engine"], cell["config"], cell["scenario"]): cell for cell in qa[size]["cells"]}
        for kind, scenarios in H1.items():
            for scenario in sorted(scenarios, key=position):
                for engine in engines(scenario):
                    names = served(plan, scenario, engine) if kind == READS else set()
                    entries.append({"scenario": scenario, "engine": engine, **evaluate(
                        kind, size, index.get((engine, "base", scenario)), index.get((engine, "idx", scenario)), names, found)})
    return entries


def verdict(entries):
    if not entries or not all(entry["complete"] for entry in entries):
        return {"verdict": None, "failing": []}
    failing = [f"{entry['scenario']} {entry['engine']}" for entry in entries if not entry["holds"]]
    return {"verdict": REJECTED if failing else CONFIRMED, "failing": failing}


def verdicts(entries):
    final = [entry for entry in entries if entry["size"] == VERDICT_SIZE]
    found = {engine: verdict([entry for entry in final if entry["engine"] == engine]) for engine in ENGINES}
    if any(entry["verdict"] is None for entry in found.values()):
        overall = {"verdict": None, "engines": [], "failing": []}
    else:
        rejected = [engine for engine, entry in found.items() if entry["verdict"] == REJECTED]
        overall = {"verdict": REJECTED if rejected else CONFIRMED, "engines": rejected,
                   "failing": [cell for engine in rejected for cell in found[engine]["failing"]]}
    return found | {"overall": overall}


def main(directory):
    source = directory / "qa.json"
    qa = json.loads(source.read_text()) if source.exists() else {}
    entries = cells(qa, plans(directory), json.loads(INDEXES.read_text())["idx"])
    result = {"cells": entries, "verdicts": verdicts(entries)}
    target = directory / "h1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    for engine, entry in result["verdicts"].items():
        failing = f" ({', '.join(entry['failing'])})" if entry["failing"] else ""
        print(f"H1 {engine}: {entry['verdict'] or 'weryfikacja po pomiarach L'}{failing}")
    print(target)
    return 0
