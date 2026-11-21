import json
import statistics
from collections import defaultdict
from hashlib import sha256

RUNS = (1, 2, 3)
CV_LIMIT = 0.15
CORE_MIN = 24
CORE_PER_OP = 6
OPS = ("C", "R", "U", "D")


def label(cell):
    return f"{cell['engine']} {cell['config']} {cell['scenario']}"


def censored(config, statuses):
    if config != "base" or "timeout" not in statuses:
        return False
    position = statuses.index("timeout")
    return set(statuses[:position]) <= {"ok"} and set(statuses[position + 1:]) <= {"skipped"}


def summary(scenario, key, runs):
    lines = [runs.get(run) for run in RUNS]
    statuses = [line["status"] if line else "missing" for line in lines]
    seconds = [line["nanoseconds"] / 1e9 if line and line.get("nanoseconds") is not None else None for line in lines]
    cell = {"engine": key["engine"], "config": key["config"], "scenario": scenario.id, "op": scenario.op,
            "qhash": key["qhash"], "state_id": key["state_id"], "statuses": statuses, "seconds": seconds}
    if statuses == ["ok"] * len(RUNS):
        mean = statistics.fmean(seconds)
        return cell | {"state": "complete", "mean": mean, "min": min(seconds), "max": max(seconds),
                       "median": statistics.median(seconds), "cv": statistics.stdev(seconds) / mean}
    return cell | {"state": "censored" if censored(key["config"], statuses) else "incomplete"}


def last(error):
    lines = (error or "").strip().splitlines()
    return lines[-1] if lines else ""


def check(cells):
    entries, problems, warnings = [], [], []
    answers = defaultdict(lambda: defaultdict(dict))
    ready, ops = defaultdict(lambda: True), {}
    for scenario, key, runs in cells:
        cell = summary(scenario, key, runs)
        entries.append(cell)
        name = label(cell)
        for run in sorted(runs):
            line = runs[run]
            if line["status"] == "error":
                problems.append(f"{name} run {run}: error: {last(line.get('error'))}")
            elif line["status"] == "timeout" and key["config"] == "idx":
                problems.append(f"{name} run {run}: timeout in IDX")
            elif line["status"] == "ok":
                if line.get("rows") == 0:
                    problems.append(f"{name} run {run}: zero rows")
                answer = line.get("hash") if scenario.read else line.get("digests") and sha256(json.dumps(line["digests"], sort_keys=True).encode()).hexdigest()
                if answer:
                    answers[scenario.id][answer][f"{key['engine']} {key['config']}"] = None
        if cell["state"] == "incomplete":
            problems.append(f"{name}: incomplete ({', '.join(cell['statuses'])})")
        elif cell["state"] == "censored":
            warnings.append(f"{name}: censored, BASE timed out ({', '.join(cell['statuses'])})")
        elif cell["cv"] > CV_LIMIT:
            warnings.append(f"{name}: CV {cell['cv']:.1%} > {CV_LIMIT:.0%}")
        ready[scenario.id] &= cell["state"] != "incomplete"
        ops[scenario.id] = scenario.op
    for scenario_id, found in answers.items():
        if len(found) > 1:
            problems.append(f"{scenario_id}: hash mismatch: "
                            + "; ".join(f"{answer[:12]} {', '.join(where)}" for answer, where in found.items()))
    core = {op: sum(1 for scenario_id, done in ready.items()
                    if done and not scenario_id.startswith("J") and ops[scenario_id] == op) for op in OPS}
    return {"cells": entries, "problems": problems, "warnings": warnings, "core_complete": core,
            "count_rule": sum(core.values()) >= CORE_MIN and min(core.values()) >= CORE_PER_OP}



def write(path, size, report):
    found = json.loads(path.read_text()) if path.exists() else {}
    found[size] = report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    for problem in report["problems"]:
        print(f"problem: {problem}")
    for warning in report["warnings"]:
        print(f"warning: {warning}")
    core = ", ".join(f"{op} {count}" for op, count in report["core_complete"].items())
    print(f"{size}: {len(report['cells'])} cells, {len(report['problems'])} problems, {len(report['warnings'])} warnings, "
          f"core complete {core}, count rule {'met' if report['count_rule'] else 'not met'}; {path}")
    return 1 if report["problems"] else 0
