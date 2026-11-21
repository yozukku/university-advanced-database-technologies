import json
import re
import time
from dataclasses import dataclass, field

CAP_SECONDS = 1800
BATCH = 1000
WORD = re.compile(r"\w+")
ARRAY_COLUMN = re.compile(r"cast\(`?(\w+)`? as .* array\)")
POLAND = [14.0, 49.0, 24.2, 55.0]
MONGO_POLAND = {"type": "Polygon", "coordinates": [[
    [POLAND[0], POLAND[1]], [POLAND[2], POLAND[1]], [POLAND[2], POLAND[3]], [POLAND[0], POLAND[3]], [POLAND[0], POLAND[1]]]]}
NEO4J_POLAND = (f"point({{longitude: {POLAND[0]}, latitude: {POLAND[1]}}}), "
                f"point({{longitude: {POLAND[2]}, latitude: {POLAND[3]}}})")
NEO4J_INDEX_OPERATORS = {"NodeIndexScan", "DirectedRelationshipIndexScan", "UndirectedRelationshipIndexScan",
                         "NodeIndexSeekByRange"}
NEO4J_SCANS = {"AllNodesScan", "NodeByLabelScan", "DirectedRelationshipTypeScan", "UndirectedRelationshipTypeScan",
               "DirectedAllRelationshipsScan", "UndirectedAllRelationshipsScan"}
UNSCANNABLE = {"spatial", "fulltext", "lookup"}
CHANGED_VALUES = """
    select distinct value from (
        select unnest(list_transform(list_filter(json_extract(changes_, '$[*]'), lambda e: json_type(e, '$.new') = 'VARCHAR'),
                                     lambda e: json_extract_string(e, '$.new'))) as value
        from audit_event_)
    order by value
"""
PG_CATALOG = """
    select t.relname, i.relname, am.amname
    from pg_class t
    left join pg_index x on x.indrelid = t.oid
    left join pg_class i on i.oid = x.indexrelid
    left join pg_am am on am.oid = i.relam
    where t.relnamespace = 'public'::regnamespace and t.relkind = 'r'
"""
MYSQL_CATALOG = """
    select t.table_name, s.index_name, s.index_type, s.expression
    from information_schema.tables t
    left join information_schema.statistics s on s.table_schema = t.table_schema and s.table_name = t.table_name
    where t.table_schema = database() and t.table_type = 'BASE TABLE'
    order by t.table_name, s.index_name, s.seq_in_index
"""
NEO4J_CATALOG = "SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties"


@dataclass(frozen=True)
class Index:
    name: str
    kind: str
    keys: tuple = ()
    predicate: str | None = None


@dataclass(frozen=True)
class Step:
    scope: str
    index: str | None
    text: str
    params: object = None


@dataclass
class Warmed:
    seconds: float
    steps: int
    skipped: list = field(default_factory=list)
    operators: dict = field(default_factory=dict)


def pg_catalog(session):
    found = {}
    for table, index, method in session.fetch(PG_CATALOG):
        indexes = found.setdefault(("table", table), [])
        if index:
            indexes.append(Index(index, method))
    return found


def mysql_catalog(session):
    found = {}
    for table, index, kind, expression in session.fetch(MYSQL_CATALOG):
        indexes = found.setdefault(("table", table), [])
        if index is None:
            continue
        column = ARRAY_COLUMN.search(expression or "")
        kind = "multi_valued" if column else kind.lower()
        if not any(item.name == index for item in indexes):
            indexes.append(Index(index, kind, (column[1],) if column else ()))
    return found


def mongo_catalog(session):
    found = {}
    for name in session.handle.list_collection_names():
        indexes = found.setdefault(("collection", name), [])
        for index in session.handle[name].list_indexes():
            key = tuple(index["key"].items())
            kind = "2dsphere" if "2dsphere" in index["key"].values() else "btree"
            predicate = json.dumps(index["partialFilterExpression"], sort_keys=True) if "partialFilterExpression" in index else None
            indexes.append(Index(index["name"], kind, key, predicate))
    return found


def neo4j_catalog(session):
    found = {("node", label): [] for label, in session.fetch("CALL db.labels()")}
    found |= {("relationship", kind): [] for kind, in session.fetch("CALL db.relationshipTypes()")}
    for name, kind, entity, scopes, properties in session.fetch(NEO4J_CATALOG):
        if scopes:
            found.setdefault((entity.lower(), scopes[0]), []).append(Index(name, kind.lower(), tuple(properties)))
    return found


CATALOGS = {"pg": pg_catalog, "mysql": mysql_catalog, "mongo": mongo_catalog, "neo4j": neo4j_catalog}


def catalog(session):
    return CATALOGS[session.engine](session)


def touched(engine, scenarios, found):
    words = set()
    for scenario in scenarios:
        words |= set(WORD.findall(scenario.impls[engine].text))
    return sorted(key for key in found if key[1] in words)


def pg_steps(found, scopes, values):
    yield Step("", None, "create extension if not exists pg_prewarm")
    for kind, table in scopes:
        yield Step(table, None, f"select pg_prewarm('{table}', 'buffer')")
        for index in sorted(found[(kind, table)], key=lambda item: item.name):
            yield Step(table, index.name, f"select pg_prewarm('{index.name}', 'buffer')")


def mysql_steps(found, scopes, values):
    for kind, table in scopes:
        for index in sorted(found[(kind, table)], key=lambda item: (item.name != "PRIMARY", item.name)):
            hinted = f"select count(*) from {table} force index (`{index.name}`)"
            if index.kind in UNSCANNABLE:
                yield Step(table, index.name, "")
            elif index.kind == "multi_valued":
                for start in range(0, len(values), BATCH):
                    yield Step(table, index.name, f"{hinted} where json_overlaps({index.keys[0]}, cast(%s as json))",
                               (json.dumps(values[start:start + BATCH]),))
            else:
                yield Step(table, index.name, hinted)


def mongo_steps(found, scopes, values):
    for kind, collection in scopes:
        yield Step(collection, None, json.dumps({"filter": {"__none": {"$exists": True}}, "hint": {"$natural": 1}}))
        for index in sorted(found[(kind, collection)], key=lambda item: item.name):
            if index.kind == "2dsphere":
                [path] = [path for path, direction in index.keys if direction == "2dsphere"]
                query = {path: {"$geoWithin": {"$geometry": MONGO_POLAND}}}
            else:
                query = json.loads(index.predicate) if index.predicate else {}
            yield Step(collection, index.name, json.dumps({"filter": query, "hint": index.name}, sort_keys=True))


def neo4j_steps(found, scopes, values):
    for kind, scope in scopes:
        pattern = f"(n:{scope})" if kind == "node" else f"()-[n:{scope}]->()"
        yield Step(scope, None, f"MATCH {pattern} WITH properties(n) AS p RETURN sum(size(keys(p)))")
        for index in sorted(found[(kind, scope)], key=lambda item: item.name):
            if index.kind in UNSCANNABLE:
                yield Step(scope, index.name, "")
                continue
            keys = ", ".join(index.keys)
            if index.kind == "point":
                [key] = index.keys
                hint, condition = "POINT", f"point.withinBBox(n.{key}, {NEO4J_POLAND})"
            else:
                hint, condition = "RANGE", " AND ".join(f"n.{key} IS NOT NULL" for key in index.keys)
            yield Step(scope, index.name, f"PROFILE MATCH {pattern} USING {hint} INDEX n:{scope}({keys}) "
                                          f"WHERE {condition} RETURN count(n.{index.keys[0]})")


STEPS = {"pg": pg_steps, "mysql": mysql_steps, "mongo": mongo_steps, "neo4j": neo4j_steps}


def script(engine, found, scenarios, values=()):
    return list(STEPS[engine](found, touched(engine, scenarios, found), list(values)))


def listing(steps):
    return [f"not warmed: {step.scope}.{step.index}" if not step.text else step.text if step.params is None
            else f"{step.text} {step.params[0]}" for step in steps]


def operators(profile):
    yield profile["operatorType"].split("@")[0], profile.get("args", {}).get("Details", "")
    for child in profile.get("children", []):
        yield from operators(child)


def neo4j_profiled(session, step):
    found = list(operators(session.handle.run(step.text).consume().profile))
    names = {name for name, _ in found}
    scope = step.text.split("INDEX n:", 1)[1].split(")", 1)[0] + ")"
    indexed = [name for name, details in found if name in NEO4J_INDEX_OPERATORS and scope in details]
    if not indexed or names & NEO4J_SCANS:
        raise RuntimeError(f"Warm-up of {step.index} runs {sorted(names)}, expected an index operator on {scope}")
    return indexed[0]


def execute(session, step):
    if session.engine == "mongo":
        command = json.loads(step.text)
        session.handle[step.scope].count_documents(command["filter"], hint=command["hint"] if isinstance(command["hint"], str)
                                                   else list(command["hint"].items()))
    elif session.engine == "neo4j" and step.text.startswith("PROFILE"):
        return neo4j_profiled(session, step)
    elif session.engine == "pg":
        session.handle.execute(step.text, step.params)
    else:
        session.fetch(step.text, step.params)
    return None


def run(session, steps, cap=CAP_SECONDS):
    start = time.perf_counter()
    warmed = Warmed(0.0, 0)
    for step in steps:
        if not step.text:
            warmed.skipped.append(f"{step.scope}.{step.index}")
            continue
        operator = execute(session, step)
        if operator:
            warmed.operators[step.index] = operator
        warmed.steps += 1
        if time.perf_counter() - start > cap:
            raise RuntimeError(f"Warm-up hit its cap of {cap} s after {warmed.steps} of {len(steps)} steps")
    warmed.seconds = time.perf_counter() - start
    return warmed
