import json

from bench.check.verify import engines as rebuild
from bench.check.verify.canonical import TABLES, kinds

from .normalise import digest, encode, row

MONGO_PATHS = {
    "lockermat_": (("lockermats", "_id"),),
    "lockermat_opening_hours_": (("lockermats", "openingHours.id"),),
    "lockermat_cell_": (("lockermats", "cells.id"),),
    "tariff_": (("tariffs", "_id"),),
    "customer_": (("customers", "_id"),),
    "order_": (("orders", "_id"),),
    "reservation_": (("orders", "reservations.id"),),
    "shipment_": (("orders", "shipment.id"),),
    "access_code_": (("orders", "reservations.accessCodes.id"),),
    "incident_": (("incidents", "_id"),),
    "cell_opening_": (("orders", "reservations.accessCodes.openings.id"), ("incidents", "serviceOpenings.id")),
    "payment_": (("orders", "payments.id"),),
    "audit_event_": (("auditEvents", "_id"),),
}
KINDS = ("inserted", "changed", "deleted")
SAMPLE = 3


class Subset:
    def __init__(self, db, filters):
        self.db = db
        self.filters = filters

    def __getattr__(self, name):
        return Found(self.db[name], self.filters.get(name))


class Found:
    def __init__(self, collection, query):
        self.collection = collection
        self.query = query

    def find(self):
        return self.collection.find(self.query) if self.query else ()


def collect(rows, schema):
    table_kinds = kinds(schema)
    found = {table: {} for table in TABLES}
    for table, values in rows:
        if table in found:
            canonical = row(table_kinds[table], values)
            found[table][canonical[0]] = encode(canonical)
    return found


def snapshot(session, schema):
    handle = session.handle
    rows = {
        "pg": lambda: rebuild.pg_rows(handle, schema),
        "mysql": lambda: rebuild.mysql_rows(handle, schema),
        "mongo": lambda: rebuild.mongo_rows(handle, schema),
        "neo4j": lambda: rebuild.neo4j_rows(handle, schema, []),
    }[session.engine]()
    return collect(rows, schema)


def sql_rows(session, schema, keys):
    point = rebuild.PG_POINT if session.engine == "pg" else rebuild.MYSQL_POINT
    for table, ids in keys.items():
        columns = rebuild.select(schema[table], point)
        for start in range(0, len(ids), 1000):
            chunk = ids[start:start + 1000]
            marks = ", ".join(["%s"] * len(chunk))
            for values in session.fetch(f"select {columns} from {table} where id_ in ({marks})", chunk):
                yield table, values


def mongo_rows(session, schema, keys):
    filters = {}
    for table, ids in keys.items():
        for collection, path in MONGO_PATHS[table]:
            filters.setdefault(collection, {"$or": []})["$or"].append({path: {"$in": ids}})
    return rebuild.mongo_rows(Subset(session.handle, filters), schema)


def neo4j_rows(session, schema, keys):
    for table, ids in keys.items():
        label, edges = rebuild.NEO4J_TABLES[table]
        key = "shipmentId" if table == "shipment_" else "id"
        ends = "".join(f", [{pattern} | e.id]" for pattern in edges.values())
        query = f"MATCH (n:{label}) WHERE n.{key} IN $keys RETURN n {{{rebuild.neo4j_projection(table, schema[table])}}}{ends}"
        for node, *found in session.fetch(query, {"keys": ids}):
            known = rebuild.neo4j_known(table, node)
            for column, ends_found in zip(edges, found, strict=True):
                known[column] = ends_found[0] if ends_found else None
            yield table, rebuild.build(schema[table], node, known)


KEYED = {"pg": sql_rows, "mysql": sql_rows, "mongo": mongo_rows, "neo4j": neo4j_rows}


def probe(session, schema, keys):
    wanted = {table: sorted(set(ids)) for table, ids in keys.items() if ids}
    unknown = set(wanted) - set(TABLES)
    if unknown:
        raise ValueError(f"Unknown tables in the key probe: {sorted(unknown)}")
    found = collect(KEYED[session.engine](session, schema, wanted), schema)
    return {table: {key: found[table][key] for key in ids if key in found[table]} for table, ids in wanted.items()}


def changes(columns, old, new):
    return {name: [before, after] for (name, _), before, after in zip(columns, json.loads(old), json.loads(new), strict=True)
            if before != after}


def diff(before, after, schema):
    found = {}
    for table in TABLES:
        old, new = before.get(table, {}), after.get(table, {})
        inserted = [[key, json.loads(new[key])] for key in sorted(new.keys() - old.keys())]
        deleted = [[key, json.loads(old[key])] for key in sorted(old.keys() - new.keys())]
        changed = [[key, changes(schema[table], old[key], new[key])]
                   for key in sorted(old.keys() & new.keys()) if old[key] != new[key]]
        if inserted or changed or deleted:
            found[table] = {"inserted": inserted, "changed": changed, "deleted": deleted}
    return found


def affected(found):
    return {table: {kind: len(entry[kind]) for kind in KINDS} for table, entry in found.items()}


def digests(found):
    return {table: digest(entry) for table, entry in found.items()}


def describe(entry):
    if entry is None:
        return "nothing"
    parts = []
    for kind in KINDS:
        keys = [key for key, _ in entry[kind]]
        if keys:
            sample = ", ".join(str(key) for key in keys[:SAMPLE]) + (", …" if len(keys) > SAMPLE else "")
            parts.append(f"{kind} {len(keys)} [{sample}]")
    return " ".join(parts)


def compare(diffs):
    problems = []
    tables = [table for table in TABLES if any(table in found for found in diffs.values())]
    for table in tables:
        entries = {label: found.get(table) for label, found in diffs.items()}
        if len({digest(entry) for entry in entries.values()}) > 1:
            problems.append(f"{table}: " + "; ".join(f"{label} {describe(entry)}" for label, entry in entries.items()))
    return problems
