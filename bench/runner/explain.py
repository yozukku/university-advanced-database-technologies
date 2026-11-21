import csv
import json
import re
import traceback

from bson import json_util

from bench.check.verify.results import root
from bench.scenarios.executor import Session
from bench.scenarios.explain import NEO4J_ACCESS, access, nodes, plan

from .matrix import CONFIGS
from .state import snapshot as state

COLUMNS = ("size", "scenario", "engine", "config", "kind", "access_path", "index", "rows_examined", "rows_returned", "file")
MYSQL_ACCESS = re.compile(r"(?:scan|lookup|search) on [^<]")
MYSQL_ACTUAL = re.compile(r"actual time=\S+ rows=([\d.e+]+) loops=(\d+)")
MONGO_SKIPPED = {"rejectedPlans", "allPlansExecution", "executionStages"}


def directory(size):
    return root(size) / "explain"


def file_name(bench, scenario, engine, config):
    return (f"{scenario.id}-{engine}-{config}-{bench.size}-{bench.qhashes[scenario.id][:12]}-"
            f"{bench.state_id(engine, config)[:12]}.json")


def wanted(bench, engine, config):
    return {file_name(bench, scenario, engine, config): scenario for scenario in bench.group(engine, config)
            if scenario.read or scenario.impls[engine].plan}


def capture(session, scenario, params):
    query = scenario.impls[session.engine].plan(params[0] if scenario.read else params)
    found = plan(session, query)
    text = None
    if session.engine == "pg":
        text = "\n".join(line for line, in session.fetch("explain (analyze, buffers) " + query.text, query.params))
    elif session.engine == "mysql":
        text = session.fetch("explain analyze " + query.text, query.params)[0][0]
    elif session.engine == "mongo":
        found = json.loads(json_util.dumps(found))
    return found, text


def run(bench):
    target = directory(bench.size)
    target.mkdir(parents=True, exist_ok=True)
    failed = []
    try:
        for engine in bench.engines:
            for config in CONFIGS:
                missing = {name: scenario for name, scenario in wanted(bench, engine, config).items()
                           if not (target / name).exists()}
                if missing:
                    failed += group(bench, target, engine, config, missing)
    finally:
        bench.stop()
    summarise(target)
    return failed


def group(bench, target, engine, config, missing):
    bench.stop()
    state.restore(engine, bench.size, config)
    bench.live = engine
    failed = []
    with Session(engine) as session:
        for name, scenario in missing.items():
            try:
                found, text = capture(session, scenario, bench.params[scenario.id])
            except Exception:
                failed.append(f"{name}: {traceback.format_exc(limit=-2)}")
                continue
            for stale in target.glob(f"{scenario.id}-{engine}-{config}-{bench.size}-*.json"):
                stale.unlink()
            entry = {"scenario": scenario.id, "engine": engine, "config": config, "size": bench.size,
                     "kind": "read" if scenario.read else "write-discovery", "qhash": bench.qhashes[scenario.id],
                     "state_id": bench.state_id(engine, config), "plan": found, "text": text}
            (target / name).write_text(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=engine != "mongo", default=str) + "\n")
            print(f"{engine} {bench.size} {config} {scenario.id}: {name}")
    return failed


def pg_rows(found, text):
    examined = sum((node["Actual Rows"] + node.get("Rows Removed by Filter", 0) + node.get("Rows Removed by Index Recheck", 0))
                   * node["Actual Loops"] for node in nodes(found) if "Relation Name" in node)
    return examined, found[0]["Plan"]["Actual Rows"]


def actual(line):
    match = MYSQL_ACTUAL.search(line)
    return round(float(match[1]) * int(match[2])) if match else 0


def mysql_rows(found, text):
    lines = text.splitlines()
    return sum(actual(line) for line in lines if MYSQL_ACCESS.search(line)), actual(lines[0])


def mongo_rows(found, text):
    examined = sum(node["totalDocsExamined"] for node in nodes(found, MONGO_SKIPPED) if "totalDocsExamined" in node)
    stages = found.get("stages")
    return examined, (stages[-1] if stages else found["executionStats"])["nReturned"]


def neo4j_rows(found, text):
    examined = sum(node["rows"] for node in nodes(found) if NEO4J_ACCESS.search(node.get("operatorType", "")))
    return examined, found["rows"]


ROWS = {"pg": pg_rows, "mysql": mysql_rows, "mongo": mongo_rows, "neo4j": neo4j_rows}


def summarise(target):
    with (target.parent / "explain_summary.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for path in sorted(target.glob("*.json")):
            entry = json.loads(path.read_text())
            found = access(entry["engine"], entry["plan"])
            writer.writerow([entry["size"], entry["scenario"], entry["engine"], entry["config"], entry["kind"],
                             "; ".join(found["access_path"]), "; ".join(found["index"]),
                             *ROWS[entry["engine"]](entry["plan"], entry["text"]), path.name])
