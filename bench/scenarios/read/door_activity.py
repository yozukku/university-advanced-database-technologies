from datetime import timezone

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("lockermat_id", "int"), ("openings", "int"), ("door_failed", "int"))
OPENING = "reservations.accessCodes.openings"
DAYS = """
    select since, since + interval 1 day
    from (select distinct date_trunc('day', requested_at_) as since from cell_opening_
          where access_code_id_ is not null and requested_at_ < date_trunc('day', getvariable('benchmark_t0')))
    order by since desc
    limit ?
"""
DOORS_PG = """
select c.lockermat_id_, count(*) as openings_, count(*) filter (where o.result_ = 'DOOR_FAILED') as door_failed_
from cell_opening_ o
join access_code_ a on a.id_ = o.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.requested_at_ >= %(since)s and o.requested_at_ < %(until)s
group by c.lockermat_id_
"""
DOORS_MYSQL = """
select c.lockermat_id_, count(*) as openings_, sum(o.result_ = 'DOOR_FAILED') as door_failed_
from cell_opening_ o
join access_code_ a on a.id_ = o.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.requested_at_ >= %(since)s and o.requested_at_ < %(until)s
group by c.lockermat_id_
"""
DOORS_MONGO = """
orders.aggregate([
  {$match: {'reservations.accessCodes.openings': {$elemMatch: {requestedAt: {$gte: :since, $lt: :until}}},
            'reservations.accessCodes.openings.requestedAt': {$exists: true}}},
  {$unwind: '$reservations'},
  {$unwind: '$reservations.accessCodes'},
  {$unwind: '$reservations.accessCodes.openings'},
  {$match: {'reservations.accessCodes.openings.requestedAt': {$gte: :since, $lt: :until}}},
  {$group: {_id: '$reservations.lockermatId', openings: {$sum: 1},
            doorFailed: {$sum: {$cond: [{$eq: ['$reservations.accessCodes.openings.result', 'DOOR_FAILED']}, 1, 0]}}}}
])
"""
DOORS_CYPHER = """
MATCH (o:CellOpening)
WHERE o.requestedAt >= $since AND o.requestedAt < $until
MATCH (o)-[:OPENED_WITH]->(:AccessCode)<-[:HAS_CODE]-(:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat)
RETURN l.id AS lockermat, count(*) AS openings, sum(CASE o.result WHEN 'DOOR_FAILED' THEN 1 ELSE 0 END) AS doorFailed
"""


def days(pick):
    found = pick.db.execute(DAYS, [pick.count]).fetchall()
    return [{"since": since.astimezone(timezone.utc), "until": until.astimezone(timezone.utc)}
            for since, until in reversed(found)]


def pipeline(parameter):
    window = {"$gte": parameter["since"], "$lt": parameter["until"]}
    return [
        {"$match": {OPENING: {"$elemMatch": {"requestedAt": window}}, f"{OPENING}.requestedAt": {"$exists": True}}},
        {"$unwind": "$reservations"},
        {"$unwind": "$reservations.accessCodes"},
        {"$unwind": f"${OPENING}"},
        {"$match": {f"{OPENING}.requestedAt": window}},
        {"$group": {"_id": "$reservations.lockermatId", "openings": {"$sum": 1},
                    "doorFailed": {"$sum": {"$cond": [{"$eq": [f"${OPENING}.result", "DOOR_FAILED"]},
                                                      1, 0]}}}},
    ]


def doors_pg(session, parameter):
    return session.fetch(DOORS_PG, parameter)


def doors_mysql(session, parameter):
    return session.fetch(DOORS_MYSQL, parameter)


def doors_mongo(session, parameter):
    return [(found["_id"], found["openings"], found["doorFailed"])
            for found in session.handle.orders.aggregate(pipeline(parameter))]


def doors_cypher(session, parameter):
    return session.fetch(DOORS_CYPHER, parameter)


SCENARIOS = [Scenario(
    id="R7", op="R", flags=frozenset({"CX", "BA", "H1-S"}), columns=COLUMNS, select=days,
    description="Aktywność drzwi każdego punktu w oknie 24 h: liczba otwarć kodem i liczba nieudanych "
                "(DOOR_FAILED), z której wynika ich udział, bez otwarć serwisowych; ×30 dni",
    impls={
        "pg": Impl(DOORS_PG, doors_pg, plan=lambda parameter: Query(DOORS_PG, parameter)),
        "mysql": Impl(DOORS_MYSQL, doors_mysql, plan=lambda parameter: Query(DOORS_MYSQL, parameter)),
        "mongo": Impl(DOORS_MONGO, doors_mongo, plan=lambda parameter: Query("orders", pipeline(parameter))),
        "neo4j": Impl(DOORS_CYPHER, doors_cypher, plan=lambda parameter: Query(DOORS_CYPHER, parameter)),
    },
)]
