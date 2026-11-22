import json
import re
from pathlib import Path

from bench.report.indexes import complete, milliseconds

MISSING = "brak danych"
LINES = 6
CONFIGS = {"base": "BASE", "idx": "IDX"}
PG_ACCESS = re.compile(r"^\s*(?:->\s+)?((?:Parallel )?(?:Seq|Index|Index Only|Bitmap Heap|Bitmap Index) Scan .*?)"
                       r"\s+\(cost=[^)]*\)\s+\(actual time=[^ ]+ (rows=\d+ loops=\d+)\)")
PG_REMOVED = re.compile(r"^\s*(Rows Removed by (?:Filter|Index Recheck): [1-9]\d*)")
MYSQL_ACCESS = re.compile(r"^\s*->\s+((?:Table scan|Index scan|Index range scan|Index lookup|Single-row index lookup|"
                          r"Covering index (?:scan|lookup|range scan)|Index search|Single-row covering index lookup)"
                          r" on .*?)\s+(?:\(cost=[^)]*\)\s+)?\(actual time=[^ ]+ (rows=[\d.e+-]+ loops=\d+)\)")
MYSQL_DETAIL = re.compile(r" (?:over )?\(.*|, with index condition: .*")
NEO4J_DETAIL = re.compile(r" WHERE .*")
MONGO_STAGES = ("COLLSCAN", "IXSCAN", "FETCH", "EXPRESS_IXSCAN", "IDHACK")
NEO4J_ACCESS = ("Scan", "Seek")


def span(results, scenario, engine, config, size="L"):
    cell = complete(results, size, scenario, engine, config)
    return f"{milliseconds(cell['min'])}–{milliseconds(cell['max'])}" if cell else None


def pg(document):
    lines = []
    for line in document["text"].splitlines():
        access, removed = PG_ACCESS.match(line), PG_REMOVED.match(line)
        if access:
            lines.append(f"{access.group(1)}  {access.group(2)}")
        elif removed and lines:
            lines.append(f"  {removed.group(1)}")
    return lines


def mysql(document):
    return [f"{MYSQL_DETAIL.sub('', found.group(1))}  {found.group(2)}"
            for found in map(MYSQL_ACCESS.match, document["text"].splitlines()) if found]


def stages(node):
    if isinstance(node, dict):
        if node.get("stage") in MONGO_STAGES and "nReturned" in node:
            yield node
        for value in node.values():
            yield from stages(value)
    elif isinstance(node, list):
        for value in node:
            yield from stages(value)


def mongo(document):
    lines = []
    for stage in stages(document["plan"]):
        name = f" {stage['indexName']}" if "indexName" in stage else ""
        examined = stage.get("keysExamined", stage.get("docsExamined"))
        unit = "keysExamined" if "keysExamined" in stage else "docsExamined"
        lines.append(f"{stage['stage']}{name}  {unit}={examined} nReturned={stage['nReturned']}")
    return lines


def operators(node):
    yield node
    for child in node.get("children", []):
        yield from operators(child)


def neo4j(document):
    return [f"{node['operatorType'].split('@')[0]}  {NEO4J_DETAIL.sub('', node['args'].get('Details', ''))}"
            f"  rows={node['args']['Rows']}"
            for node in operators(document["plan"]) if any(word in node["operatorType"] for word in NEO4J_ACCESS)]


EXCERPTS = {"pg": pg, "mysql": mysql, "mongo": mongo, "neo4j": neo4j}


def excerpt(results, scenario, engine, config, size):
    found = sorted((Path(results) / "explain").glob(f"{scenario}-{engine}-{config}-{size}-*.json"))
    if not found:
        return [MISSING]
    lines = EXCERPTS[engine](json.loads(found[-1].read_text(encoding="utf-8")))
    return lines[:LINES] + (["…"] if len(lines) > LINES else [])


def plan(results, scenario, engine, size, caption):
    parts = {label: excerpt(results, scenario, engine, config, size) for config, label in CONFIGS.items()}
    body = MISSING if all(lines == [MISSING] for lines in parts.values()) else "\n\n".join(
        "\n".join([f"{label}:", *(f"  {line}" for line in lines)]) for label, lines in parts.items())
    name = f"plan-{scenario}-{engine}"
    return f"::: {{#fig:{name} .figure .listing}}\n```\n{body}\n```\n\n{caption}\n:::"


VALUES = {"span": span}
