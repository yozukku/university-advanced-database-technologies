from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

PENDING = """
select x.id_
from cell_opening_ x
join access_code_ a on a.id_ = x.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
where x.result_ = 'PENDING' and a.status_ = 'ACTIVE' and a.purpose_ = 'DROP_OFF' and r.status_ = 'BOOKED'
order by x.id_
"""
GRANTS_SQL = """
select x.id_, a.id_, a.reservation_id_
from cell_opening_ x
join access_code_ a on a.id_ = x.access_code_id_
where x.id_ in ({marks})
"""
LOCK_PG = """
select o.id_
from cell_opening_ x
join access_code_ a on a.id_ = x.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join order_ o on o.id_ = r.order_id_
where x.id_ = %(opening)s
for update of o
"""
REDEEM_PG = """
with opening as (
    update cell_opening_ set result_ = 'OPENED'
    where id_ = %(opening)s and result_ = 'PENDING'
    returning access_code_id_, requested_at_
), code as (
    update access_code_ a set status_ = 'USED', used_at_ = o.requested_at_
    from opening o
    where a.id_ = o.access_code_id_ and a.status_ = 'ACTIVE' and a.purpose_ = 'DROP_OFF'
    returning a.reservation_id_, o.requested_at_
)
update reservation_ r
set status_ = 'OCCUPIED', deposited_at_ = c.requested_at_
from code c
where r.id_ = c.reservation_id_ and r.status_ = 'BOOKED'
returning r.id_
"""
LOCK_MYSQL = """
select a.id_, r.id_, x.requested_at_
from cell_opening_ x
join access_code_ a on a.id_ = x.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join order_ o on o.id_ = r.order_id_
where x.id_ = %(opening)s
for update of o
"""
OPEN_MYSQL = "update cell_opening_ set result_ = 'OPENED' where id_ = %(opening)s and result_ = 'PENDING'"
USE_MYSQL = """
update access_code_ set status_ = 'USED', used_at_ = %(at)s
where id_ = %(code)s and status_ = 'ACTIVE' and purpose_ = 'DROP_OFF'
"""
DEPOSIT_MYSQL = """
update reservation_ set status_ = 'OCCUPIED', deposited_at_ = %(at)s
where id_ = %(leg)s and status_ = 'BOOKED'
"""
REDEEM_MYSQL = ";\n".join(text.strip() for text in (LOCK_MYSQL, OPEN_MYSQL, USE_MYSQL, DEPOSIT_MYSQL))
OPENING = "reservations.accessCodes.openings"
REDEEM_MONGO = """
orders.findOne({'reservations.accessCodes.openings.id': :opening}, {<id nogi, kodu i otwarcia, skrytka, punkt, requestedAt>});
lockermats.updateOne({_id: <lockermatId nogi>, 'cells.id': <cellId nogi>}, {$inc: {'cells.$.guardSeq': 1}});
orders.findOne({reservations: {$elemMatch: {cellId: <cellId nogi>, depositedAt: {$exists: true},
                                           $or: [{collectedAt: {$exists: false}}, {collectedAt: {$gt: <requestedAt>}}]}}});
orders.updateOne({_id: <id zamówienia>, reservations: {$elemMatch: {id: <id nogi>, status: 'BOOKED', accessCodes: {$elemMatch: {
                      id: <id kodu>, status: 'ACTIVE', purpose: 'DROP_OFF', openings: {$elemMatch: {id: :opening, result: 'PENDING'}}}}}}},
                 {$set: {'reservations.$[leg].status': 'OCCUPIED', 'reservations.$[leg].depositedAt': <requestedAt>,
                         'reservations.$[leg].accessCodes.$[code].status': 'USED',
                         'reservations.$[leg].accessCodes.$[code].usedAt': <requestedAt>,
                         'reservations.$[leg].accessCodes.$[code].openings.$[opening].result': 'OPENED'}},
                 {arrayFilters: [{'leg.id': <id nogi>}, {'code.id': <id kodu>}, {'opening.id': :opening}]})
// jedna transakcja na użycie kodu
"""
REDEEM_CYPHER = """
MATCH (x:CellOpening {id: $opening})-[:OPENED_WITH]->(a:AccessCode)<-[:HAS_CODE]-(r:Reservation)-[:IN_CELL]->(c:Cell)
WHERE x.result = 'PENDING' AND a.status = 'ACTIVE' AND a.purpose = 'DROP_OFF' AND r.status = 'BOOKED'
SET c._guard = coalesce(c._guard, 0) + 1
WITH x, a, r, c
WHERE NOT EXISTS {
    MATCH (c)<-[:IN_CELL]-(y:Reservation)
    WHERE y.depositedAt IS NOT NULL AND (y.collectedAt IS NULL OR y.collectedAt > x.requestedAt)
}
SET x.result = 'OPENED', a.status = 'USED', a.usedAt = x.requestedAt,
    r.status = 'OCCUPIED', r.depositedAt = x.requestedAt
RETURN r.id
"""
GRANTS_CYPHER = """
MATCH (x:CellOpening)-[:OPENED_WITH]->(a:AccessCode)<-[:HAS_CODE]-(r:Reservation)
WHERE x.id IN $openings
RETURN x.id, a.id, r.id
"""
GRANT_PATHS = {"_id": 1, "reservations.id": 1, "reservations.cellId": 1, "reservations.lockermatId": 1,
               "reservations.accessCodes.id": 1, f"{OPENING}.id": 1, f"{OPENING}.requestedAt": 1}


def pending(pick):
    ids = [opening for opening, in pick.db.execute(PENDING).fetchall()]
    chosen = pick.rng.choice(len(ids), pick.count, replace=False)
    return chunks([ids[index] for index in chosen], pick.config["batch"])


def every_opening(params):
    return [opening for batch in params for opening in batch]


def grants(rows):
    openings, codes, legs = zip(*rows) if rows else ((), (), ())
    return {"cell_opening_": list(openings), "access_code_": list(codes), "reservation_": list(legs)}


def keys_sql(session, params):
    openings = every_opening(params)
    return grants(session.fetch(GRANTS_SQL.format(marks=", ".join(["%s"] * len(openings))), openings))


def located(order, opening):
    for leg in order["reservations"]:
        for code in leg.get("accessCodes", ()):
            for found in code.get("openings", ()):
                if found["id"] == opening:
                    return leg, code, found
    raise RuntimeError(f"Opening {opening} is not in order {order['_id']}")


def keys_mongo(session, params):
    wanted = set(every_opening(params))
    rows = []
    for order in session.handle.orders.find({f"{OPENING}.id": {"$in": sorted(wanted)}}, GRANT_PATHS):
        for leg in order["reservations"]:
            for code in leg.get("accessCodes", ()):
                rows.extend((found["id"], code["id"], leg["id"]) for found in code.get("openings", ())
                            if found["id"] in wanted)
    return grants(rows)


def keys_cypher(session, params):
    return grants(session.fetch(GRANTS_CYPHER, {"openings": every_opening(params)}))


def redeemed(count, opening):
    if count != 1:
        raise RuntimeError(f"Opening {opening} was not redeemed ({count} rows)")


def redeem_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            for opening in batch:
                conn.execute(LOCK_PG, {"opening": opening}).fetchall()
                redeemed(len(conn.execute(REDEEM_PG, {"opening": opening}).fetchall()), opening)
                session.driver_counts["reservation_"] += 1


def redeem_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            for opening in batch:
                cursor.execute(LOCK_MYSQL, {"opening": opening})
                [(code, leg, at)] = cursor.fetchall()
                for text in (OPEN_MYSQL, USE_MYSQL, DEPOSIT_MYSQL):
                    cursor.execute(text, {"opening": opening, "code": code, "leg": leg, "at": at})
                    redeemed(cursor.rowcount, opening)
                session.driver_counts["reservation_"] += 1


def redeem_mongo(session, params):
    db = session.handle
    for batch in params:
        with session.transaction() as transaction:
            for opening in batch:
                order = db.orders.find_one({f"{OPENING}.id": opening}, GRANT_PATHS, session=transaction)
                leg, code, found = located(order, opening)
                at = found["requestedAt"]
                db.lockermats.update_one({"_id": leg["lockermatId"], "cells.id": leg["cellId"]},
                                         {"$inc": {"cells.$.guardSeq": 1}}, session=transaction)
                occupied = {"cellId": leg["cellId"], "depositedAt": {"$exists": True},
                            "$or": [{"collectedAt": {"$exists": False}}, {"collectedAt": {"$gt": at}}]}
                if db.orders.find_one({"reservations": {"$elemMatch": occupied}}, {"_id": 1}, session=transaction):
                    raise RuntimeError(f"Cell {leg['cellId']} is occupied, opening {opening}")
                grant = {"id": code["id"], "status": "ACTIVE", "purpose": "DROP_OFF",
                         "openings": {"$elemMatch": {"id": opening, "result": "PENDING"}}}
                done = db.orders.update_one(
                    {"_id": order["_id"],
                     "reservations": {"$elemMatch": {"id": leg["id"], "status": "BOOKED",
                                                     "accessCodes": {"$elemMatch": grant}}}},
                    {"$set": {"reservations.$[leg].status": "OCCUPIED", "reservations.$[leg].depositedAt": at,
                              "reservations.$[leg].accessCodes.$[code].status": "USED",
                              "reservations.$[leg].accessCodes.$[code].usedAt": at,
                              "reservations.$[leg].accessCodes.$[code].openings.$[opening].result": "OPENED"}},
                    array_filters=[{"leg.id": leg["id"]}, {"code.id": code["id"]}, {"opening.id": opening}],
                    session=transaction)
                redeemed(done.modified_count, opening)
                session.driver_counts["orders"] += 1


def redeem_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            for opening in batch:
                redeemed(len(tx.run(REDEEM_CYPHER, opening=opening).values()), opening)
                session.driver_counts["reservations"] += 1


SCENARIOS = [Scenario(
    id="U2", op="U", select=pending,
    description="Użycie kodu nadania ×1000: otwarcie skrytki → OPENED, kod → USED, noga → OCCUPIED "
                "w jednej transakcji, z kontrolą faktycznego zajęcia skrytki",
    impls={
        "pg": Impl(f"{LOCK_PG.strip()};\n{REDEEM_PG}", redeem_pg, keys=keys_sql),
        "mysql": Impl(REDEEM_MYSQL, redeem_mysql, keys=keys_sql),
        "mongo": Impl(REDEEM_MONGO, redeem_mongo, keys=keys_mongo),
        "neo4j": Impl(REDEEM_CYPHER, redeem_cypher, keys=keys_cypher),
    },
)]
