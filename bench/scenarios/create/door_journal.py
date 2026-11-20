from datetime import timedelta

from bson import Int64
from pymongo import UpdateOne

from bench.scenarios.params import chunks, fresh_id
from bench.scenarios.registry import Impl, Scenario

CODES = """
select id_ from access_code_
where status_ = 'ACTIVE' and valid_from_ <= getvariable('benchmark_t0')
  and valid_to_ > getvariable('benchmark_t0') + to_milliseconds(?)
order by id_
"""
APPEND_PG = """
insert into cell_opening_ (id_, access_code_id_, channel_, result_, requested_at_)
select * from unnest(%(id)s::bigint[], %(code)s::bigint[], %(channel)s::varchar[], %(result)s::varchar[],
                     %(at)s::timestamptz[])
"""
APPEND_MYSQL = """
insert into cell_opening_ (id_, access_code_id_, channel_, result_, requested_at_)
values (%s, %s, %s, %s, %s)
"""
APPEND_MONGO = ("orders.bulkWrite([{updateOne: {filter: {'reservations.accessCodes.id': :code}, "
                "update: {$push: {'reservations.$[leg].accessCodes.$[code].openings': {id, channel, result, requestedAt}}}, "
                "arrayFilters: [{'leg.accessCodes.id': :code}, {'code.id': :code}]}}, …]) in one transaction per batch")
APPEND_CYPHER = """
UNWIND $rows AS row
MATCH (a:AccessCode {id: row.code})
CREATE (:CellOpening {id: row.id, channel: row.channel, result: row.result, requestedAt: row.at})-[:OPENED_WITH]->(a)
"""
FIELDS = ("id", "code", "channel", "result", "at")


def openings(pick):
    codes = [code for code, in pick.db.execute(CODES, [pick.count]).fetchall()]
    rows = [{"id": fresh_id(n), "code": codes[(n - 1) % len(codes)], "channel": "KEYPAD", "result": "DOOR_FAILED",
             "at": pick.t0 + timedelta(milliseconds=n)} for n in range(1, pick.count + 1)]
    return chunks(rows, pick.config["batch"])


def keys(session, params):
    return {"cell_opening_": [row["id"] for batch in params for row in batch]}


def append_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            columns = {field: [row[field] for row in batch] for field in FIELDS}
            session.driver_counts["cell_opening_"] += conn.execute(APPEND_PG, columns).rowcount


def append_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.executemany(APPEND_MYSQL, [tuple(row[field] for field in FIELDS) for row in batch])
            session.driver_counts["cell_opening_"] += cursor.rowcount


def push(row):
    opening = {"id": Int64(row["id"]), "channel": row["channel"], "result": row["result"], "requestedAt": row["at"]}
    return UpdateOne({"reservations.accessCodes.id": row["code"]},
                     {"$push": {"reservations.$[leg].accessCodes.$[code].openings": opening}},
                     array_filters=[{"leg.accessCodes.id": row["code"]}, {"code.id": row["code"]}])


def append_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            done = session.handle.orders.bulk_write([push(row) for row in batch], session=transaction)
            session.driver_counts["orders"] += done.modified_count


def append_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            session.driver_counts["nodes"] += tx.run(APPEND_CYPHER, rows=batch).consume().counters.nodes_created


SCENARIOS = [Scenario(
    id="C2", op="C", select=openings, flags=frozenset({"BA", "H1-I"}),
    description="Dopisanie 100 000 wpisów dziennika drzwi (nieudane otwarcia kodem z klawiatury) "
                "partiami po 1000 w jednej transakcji na partię",
    impls={
        "pg": Impl(APPEND_PG, append_pg, keys=keys),
        "mysql": Impl(APPEND_MYSQL, append_mysql, keys=keys),
        "mongo": Impl(APPEND_MONGO, append_mongo, keys=keys),
        "neo4j": Impl(APPEND_CYPHER, append_cypher, keys=keys),
    },
)]
