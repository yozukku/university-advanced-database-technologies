from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

EXPIRED_SQL = "select id_ from access_code_ where status_ = 'ACTIVE' and valid_to_ < %(now)s order by id_"
REVOKE_PG = "update access_code_ set status_ = 'REVOKED' where id_ = any(%(codes)s) and status_ = 'ACTIVE'"
REVOKE_MYSQL = "update access_code_ set status_ = 'REVOKED' where id_ in ({marks}) and status_ = 'ACTIVE'"
CODE = "reservations.accessCodes"
REVOKE_MONGO = """
orders.aggregate([{$match: {'reservations.accessCodes': {$elemMatch: {status: 'ACTIVE', validTo: {$lt: :now}}}}},
                  {$unwind: '$reservations'}, {$unwind: '$reservations.accessCodes'},
                  {$match: {'reservations.accessCodes.status': 'ACTIVE', 'reservations.accessCodes.validTo': {$lt: :now}}},
                  {$project: {_id: 0, id: '$reservations.accessCodes.id'}}, {$sort: {id: 1}}]);
orders.updateMany({'reservations.accessCodes.id': {$in: <partia 5000 id>}},
                  {$set: {'reservations.$[leg].accessCodes.$[code].status': 'REVOKED'}},
                  {arrayFilters: [{'leg.accessCodes': {$exists: true}},
                                  {'code.id': {$in: <partia 5000 id>}, 'code.status': 'ACTIVE'}]})
// jedna transakcja na partię
"""
EXPIRED_CYPHER = """
MATCH (a:AccessCode)
WHERE a.status = 'ACTIVE' AND a.validTo < $now
RETURN a.id ORDER BY a.id
"""
REVOKE_CYPHER = """
UNWIND $codes AS id
MATCH (a:AccessCode {id: id})
WHERE a.status = 'ACTIVE'
SET a.status = 'REVOKED'
"""


def cutoff(pick):
    return {"now": pick.t0, "batch": pick.config["batch"]}


def expired_mongo(now):
    active = {"status": "ACTIVE", "validTo": {"$lt": now}}
    return [
        {"$match": {CODE: {"$elemMatch": active}}},
        {"$unwind": "$reservations"}, {"$unwind": f"${CODE}"},
        {"$match": {f"{CODE}.{field}": value for field, value in active.items()}},
        {"$project": {"_id": 0, "id": f"${CODE}.id"}}, {"$sort": {"id": 1}},
    ]


def expired_sql(session, params):
    return [row[0] for row in session.fetch(EXPIRED_SQL, {"now": params["now"]})]


def expired_cypher(session, params):
    return [row[0] for row in session.fetch(EXPIRED_CYPHER, {"now": params["now"]})]


def expired_mongo_ids(session, params):
    return [found["id"] for found in session.handle.orders.aggregate(expired_mongo(params["now"]))]


def keys_sql(session, params):
    return {"access_code_": expired_sql(session, params)}


def keys_mongo(session, params):
    return {"access_code_": expired_mongo_ids(session, params)}


def keys_cypher(session, params):
    return {"access_code_": expired_cypher(session, params)}


def revoke_pg(session, params):
    for batch in chunks(expired_sql(session, params), params["batch"]):
        with session.transaction() as conn:
            session.driver_counts["access_code_"] += conn.execute(REVOKE_PG, {"codes": batch}).rowcount


def revoke_mysql(session, params):
    for batch in chunks(expired_sql(session, params), params["batch"]):
        with session.transaction() as cursor:
            cursor.execute(REVOKE_MYSQL.format(marks=", ".join(["%s"] * len(batch))), batch)
            session.driver_counts["access_code_"] += cursor.rowcount


def revoke_mongo(session, params):
    for batch in chunks(expired_mongo_ids(session, params), params["batch"]):
        with session.transaction() as transaction:
            done = session.handle.orders.update_many(
                {f"{CODE}.id": {"$in": batch}}, {"$set": {"reservations.$[leg].accessCodes.$[code].status": "REVOKED"}},
                array_filters=[{"leg.accessCodes": {"$exists": True}}, {"code.id": {"$in": batch}, "code.status": "ACTIVE"}],
                session=transaction)
            session.driver_counts["orders"] += done.modified_count


def revoke_cypher(session, params):
    for batch in chunks(expired_cypher(session, params), params["batch"]):
        with session.transaction() as tx:
            session.driver_counts["properties"] += tx.run(REVOKE_CYPHER, codes=batch).consume().counters.properties_set


SCENARIOS = [Scenario(
    id="U6", op="U", select=cutoff,
    description="Unieważnienie wszystkich aktywnych kodów dostępu po upływie ich ważności (ACTIVE → REVOKED), "
                "partiami po 5000 kodów",
    impls={
        "pg": Impl(f"{EXPIRED_SQL};\n{REVOKE_PG}", revoke_pg, keys=keys_sql),
        "mysql": Impl(f"{EXPIRED_SQL};\n{REVOKE_MYSQL}", revoke_mysql, keys=keys_sql),
        "mongo": Impl(REVOKE_MONGO, revoke_mongo, keys=keys_mongo),
        "neo4j": Impl(f"{EXPIRED_CYPHER.strip()};\n{REVOKE_CYPHER}", revoke_cypher, keys=keys_cypher),
    },
)]
