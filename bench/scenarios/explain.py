import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

INDEXES = Path("docs/bench/indexes.yaml")
SKIPPED = {"rejectedPlans", "allPlansExecution", "slotBasedPlan", "executionStats"}
NEO4J_ACCESS = re.compile(r"Scan|Seek")
NEO4J_INDEX = re.compile(r"\b\w+:(\w+)\(([^)]*)\)")
MYSQL_MERGED = re.compile(r"(\w+)(?=[,)])")


@dataclass(frozen=True)
class Query:
    text: str
    params: Any = None


def plan(session, query):
    engine = session.engine
    if engine == "pg":
        return session.fetch("explain (analyze, buffers, format json) " + query.text, query.params)[0][0]
    if engine == "mysql":
        return json.loads(session.fetch("explain format=json " + query.text, query.params)[0][0])
    if engine == "mongo":
        if isinstance(query.params, list):
            command = {"aggregate": query.text, "pipeline": query.params, "cursor": {}}
        else:
            command = {"find": query.text, "filter": query.params or {}}
        return session.handle.command("explain", command, verbosity="executionStats")
    result = session.handle.run("PROFILE " + query.text, query.params)
    result.values()
    return result.consume().profile


def nodes(item, skipped=frozenset()):
    if isinstance(item, dict):
        yield item
        for key, value in item.items():
            if key not in skipped:
                yield from nodes(value, skipped)
    elif isinstance(item, list):
        for value in item:
            yield from nodes(value, skipped)


def pg_access(found):
    for node in nodes(found):
        if "Relation Name" in node or "Index Name" in node:
            yield node["Node Type"], node.get("Index Name")


def mysql_access(found):
    for node in nodes(found):
        if "access_type" in node:
            key = node.get("key")
            for index in MYSQL_MERGED.findall(key) if key and node["access_type"] == "index_merge" else [key]:
                yield node["access_type"], index


def mongo_access(found):
    for node in nodes(found):
        if "winningPlan" in node:
            for stage in nodes(node["winningPlan"], SKIPPED):
                if "stage" in stage and (stage["stage"].endswith("SCAN") or "indexName" in stage or "IDHACK" in stage["stage"]):
                    yield stage["stage"], stage.get("indexName")


@cache
def neo4j_names():
    indexes = json.loads(INDEXES.read_text())
    groups = [*indexes["base"].values(), *indexes["base_extras"].values(), *(entry["engines"] for entry in indexes["idx"].values())]
    return {(item["scope"], tuple(item["keys"])): item["name"]
            for group in groups if isinstance(group.get("neo4j"), list)
            for item in group["neo4j"] if "keys" in item}


def neo4j_access(found):
    for node in nodes(found):
        operator = node.get("operatorType", "").split("@")[0]
        if NEO4J_ACCESS.search(operator):
            details = node.get("args", {}).get("Details", "")
            match = NEO4J_INDEX.search(details) if "INDEX" in details or "UNIQUE" in details else None
            index = None
            if match:
                key = (match[1], tuple(part.strip() for part in match[2].split(",")))
                index = neo4j_names().get(key, f"{key[0]}({', '.join(key[1])})")
            yield operator, index


EXTRACT = {"pg": pg_access, "mysql": mysql_access, "mongo": mongo_access, "neo4j": neo4j_access}


def unique(values):
    return list(dict.fromkeys(value for value in values if value is not None))


def access(engine, found):
    pairs = list(EXTRACT[engine](found))
    return {"access_path": unique(path for path, _ in pairs), "index": unique(index for _, index in pairs)}


def explain(session, query):
    return access(session.engine, plan(session, query))
