from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

LOCKERS = """
select distinct c.lockermat_id_
from reservation_ r
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
where l.status_ = 'ACTIVE' and r.status_ = 'BOOKED' and r.from_ > getvariable('benchmark_t0')
  and exists (select 1 from access_code_ a where a.reservation_id_ = r.id_ and a.status_ = 'ACTIVE')
order by 1
"""
DECOMMISSION_PG = """
with cells as (
    update lockermat_cell_ set status_ = 'OUT_OF_SERVICE'
    where lockermat_id_ = any(%(lockers)s) and status_ = 'IN_SERVICE'
), legs as (
    update reservation_ r set status_ = 'CANCELLED'
    from lockermat_cell_ c
    where c.id_ = r.cell_id_ and c.lockermat_id_ = any(%(lockers)s) and r.status_ = 'BOOKED' and r.from_ > %(now)s
    returning r.id_
)
update access_code_ a set status_ = 'REVOKED'
from legs l
where a.reservation_id_ = l.id_ and a.status_ = 'ACTIVE'
"""
DECOMMISSION_MYSQL = """
update lockermat_cell_ c
left join reservation_ r on r.cell_id_ = c.id_ and r.status_ = 'BOOKED' and r.from_ > %s
left join access_code_ a on a.reservation_id_ = r.id_ and a.status_ = 'ACTIVE'
set c.status_ = 'OUT_OF_SERVICE', r.status_ = 'CANCELLED', a.status_ = 'REVOKED'
where c.lockermat_id_ in ({marks})
"""
DECOMMISSION_MONGO = """
lockermats.find({_id: {$in: :lockers}}, {'cells.id': 1});
lockermats.updateMany({_id: {$in: :lockers}}, {$set: {'cells.$[cell].status': 'OUT_OF_SERVICE'}},
                      {arrayFilters: [{'cell.status': 'IN_SERVICE'}]});
orders.updateMany({reservations: {$elemMatch: {cellId: {$in: <cells>}, status: 'BOOKED', from: {$gt: :now}}}},
                  {$set: {'reservations.$[leg].accessCodes.$[code].status': 'REVOKED'}},
                  {arrayFilters: [{'leg.cellId': {$in: <cells>}, 'leg.status': 'BOOKED', 'leg.from': {$gt: :now},
                                   'leg.accessCodes': {$exists: true}}, {'code.status': 'ACTIVE'}]});
orders.updateMany({reservations: {$elemMatch: {cellId: {$in: <cells>}, status: 'BOOKED', from: {$gt: :now}}}},
                  {$set: {'reservations.$[leg].status': 'CANCELLED'}},
                  {arrayFilters: [{'leg.cellId': {$in: <cells>}, 'leg.status': 'BOOKED', 'leg.from': {$gt: :now}}]})
in one transaction per batch
"""
DECOMMISSION_CYPHER = """
MATCH (l:Lockermat)-[:HAS_CELL]->(c:Cell)
WHERE l.id IN $lockers
SET c.status = 'OUT_OF_SERVICE'
WITH c
MATCH (c)<-[:IN_CELL]-(r:Reservation)
WHERE r.status = 'BOOKED' AND r.from > $now
SET r.status = 'CANCELLED'
WITH r
MATCH (r)-[:HAS_CODE]->(a:AccessCode)
WHERE a.status = 'ACTIVE'
SET a.status = 'REVOKED'
"""
TARGETS_SQL = """
select c.id_, r.id_, a.id_
from lockermat_cell_ c
left join reservation_ r on r.cell_id_ = c.id_ and r.status_ = 'BOOKED' and r.from_ > %s
left join access_code_ a on a.reservation_id_ = r.id_ and a.status_ = 'ACTIVE'
where c.lockermat_id_ in ({marks})
"""
TARGETS_CYPHER = """
MATCH (l:Lockermat)-[:HAS_CELL]->(c:Cell)
WHERE l.id IN $lockers
OPTIONAL MATCH (c)<-[:IN_CELL]-(r:Reservation)
WHERE r.status = 'BOOKED' AND r.from > $now
OPTIONAL MATCH (r)-[:HAS_CODE]->(a:AccessCode)
WHERE a.status = 'ACTIVE'
RETURN c.id, r.id, a.id
"""
TABLES = ("lockermat_cell_", "reservation_", "access_code_")


def lockers(pick):
    ids = [locker for locker, in pick.db.execute(LOCKERS).fetchall()]
    chosen = sorted(ids[index] for index in pick.rng.choice(len(ids), pick.count, replace=False))
    return {"now": pick.t0, "lockers": chunks(chosen, pick.config["batch"])}


def every_locker(params):
    return [locker for batch in params["lockers"] for locker in batch]


def marks(values):
    return ", ".join(["%s"] * len(values))


def targets(rows):
    return {table: sorted({row[position] for row in rows if row[position] is not None})
            for position, table in enumerate(TABLES)}


def keys_sql(session, params):
    found = every_locker(params)
    return targets(session.fetch(TARGETS_SQL.format(marks=marks(found)), [params["now"], *found]))


def booked(cells, now):
    return {"cellId": {"$in": cells}, "status": "BOOKED", "from": {"$gt": now}}


def leg_filter(cells, now):
    return {f"leg.{field}": condition for field, condition in booked(cells, now).items()}


def cells_mongo(session, batch, transaction=None):
    return [cell["id"] for locker in session.handle.lockermats.find({"_id": {"$in": batch}}, {"cells.id": 1},
                                                                    session=transaction)
            for cell in locker["cells"]]


def keys_mongo(session, params):
    cells = cells_mongo(session, every_locker(params))
    condition = booked(cells, params["now"])
    legs = list(session.handle.orders.aggregate([
        {"$match": {"reservations": {"$elemMatch": condition}}},
        {"$unwind": "$reservations"},
        {"$match": {f"reservations.{field}": value for field, value in condition.items()}},
        {"$project": {"_id": 0, "leg": "$reservations.id", "codes": "$reservations.accessCodes"}},
    ]))
    return {"lockermat_cell_": sorted(cells), "reservation_": sorted(found["leg"] for found in legs),
            "access_code_": sorted(code["id"] for found in legs for code in found.get("codes", ())
                                   if code["status"] == "ACTIVE")}


def keys_cypher(session, params):
    return targets(session.fetch(TARGETS_CYPHER, {"lockers": every_locker(params), "now": params["now"]}))


def decommission_pg(session, params):
    for batch in params["lockers"]:
        with session.transaction() as conn:
            session.driver_counts["access_code_"] += conn.execute(DECOMMISSION_PG, {"lockers": batch,
                                                                                    "now": params["now"]}).rowcount


def decommission_mysql(session, params):
    for batch in params["lockers"]:
        with session.transaction() as cursor:
            cursor.execute(DECOMMISSION_MYSQL.format(marks=marks(batch)), [params["now"], *batch])
            session.driver_counts["rows"] += cursor.rowcount


def decommission_mongo(session, params):
    db = session.handle
    now = params["now"]
    for batch in params["lockers"]:
        with session.transaction() as transaction:
            cells = cells_mongo(session, batch, transaction)
            done = db.lockermats.update_many({"_id": {"$in": batch}},
                                             {"$set": {"cells.$[cell].status": "OUT_OF_SERVICE"}},
                                             array_filters=[{"cell.status": "IN_SERVICE"}], session=transaction)
            session.driver_counts["lockermats"] += done.modified_count
            legs = {"reservations": {"$elemMatch": booked(cells, now)}}
            done = db.orders.update_many(legs, {"$set": {"reservations.$[leg].accessCodes.$[code].status": "REVOKED"}},
                                         array_filters=[leg_filter(cells, now) | {"leg.accessCodes": {"$exists": True}},
                                                        {"code.status": "ACTIVE"}], session=transaction)
            session.driver_counts["codes"] += done.modified_count
            done = db.orders.update_many(legs, {"$set": {"reservations.$[leg].status": "CANCELLED"}},
                                         array_filters=[leg_filter(cells, now)], session=transaction)
            session.driver_counts["legs"] += done.modified_count


def decommission_cypher(session, params):
    for batch in params["lockers"]:
        with session.transaction() as tx:
            counters = tx.run(DECOMMISSION_CYPHER, lockers=batch, now=params["now"]).consume().counters
            session.driver_counts["properties"] += counters.properties_set


SCENARIOS = [Scenario(
    id="U4", op="U", select=lockers,
    description="Wycofanie 20 automatów z eksploatacji w jednej transakcji: ich skrytki → OUT_OF_SERVICE, "
                "przyszłe zarezerwowane nogi → CANCELLED, aktywne kody tych nóg → REVOKED",
    impls={
        "pg": Impl(DECOMMISSION_PG, decommission_pg, keys=keys_sql),
        "mysql": Impl(DECOMMISSION_MYSQL, decommission_mysql, keys=keys_sql),
        "mongo": Impl(DECOMMISSION_MONGO, decommission_mongo, keys=keys_mongo),
        "neo4j": Impl(DECOMMISSION_CYPHER, decommission_cypher, keys=keys_cypher),
    },
)]
