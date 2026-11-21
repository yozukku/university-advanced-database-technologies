from datetime import timedelta

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("lockermat_id", "int"), ("orders", "int"))
LEGS = ["STORAGE", "ORIGIN"]
RANKING_SQL = """
select c.lockermat_id_, count(*) as orders_
from order_ o
join reservation_ r on r.order_id_ = o.id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.status_ = 'COMPLETED' and o.created_at_ >= %(since)s and o.created_at_ < %(now)s
  and r.leg_ in ('STORAGE', 'ORIGIN')
group by c.lockermat_id_
order by orders_ desc, c.lockermat_id_
limit %(limit)s
"""
RANKING_MONGO = """
orders.aggregate([
  {$match: {status: 'COMPLETED', createdAt: {$gte: :since, $lt: :now}}},
  {$unwind: '$reservations'},
  {$match: {'reservations.leg': {$in: ['STORAGE', 'ORIGIN']}}},
  {$group: {_id: '$reservations.lockermatId', orders: {$sum: 1}}},
  {$sort: {orders: -1, _id: 1}},
  {$limit: :limit}
])
"""
RANKING_CYPHER = """
MATCH (o:Order)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat)
WHERE o.status = 'COMPLETED' AND o.createdAt >= $since AND o.createdAt < $now AND r.leg IN ['STORAGE', 'ORIGIN']
RETURN l.id AS lockermat, count(*) AS orders
ORDER BY orders DESC, lockermat
LIMIT $limit
"""


def window(pick):
    since = pick.t0 - timedelta(days=pick.config["days"])
    return [{"since": since, "now": pick.t0, "limit": pick.config["limit"]}] * pick.count


def pipeline(parameter):
    return [
        {"$match": {"status": "COMPLETED", "createdAt": {"$gte": parameter["since"], "$lt": parameter["now"]}}},
        {"$unwind": "$reservations"},
        {"$match": {"reservations.leg": {"$in": LEGS}}},
        {"$group": {"_id": "$reservations.lockermatId", "orders": {"$sum": 1}}},
        {"$sort": {"orders": -1, "_id": 1}},
        {"$limit": parameter["limit"]},
    ]


def ranking_sql(session, parameter):
    return session.fetch(RANKING_SQL, parameter)


def ranking_mongo(session, parameter):
    return [(found["_id"], found["orders"]) for found in session.handle.orders.aggregate(pipeline(parameter))]


def ranking_cypher(session, parameter):
    return session.fetch(RANKING_CYPHER, parameter)


def sql_plan(parameter):
    return Query(RANKING_SQL, parameter)


SCENARIOS = [Scenario(
    id="R5", op="R", flags=frozenset({"CX", "BA", "H1-S"}), columns=COLUMNS, ordered=True, select=window,
    description="Ranking 20 punktów według liczby zamówień utworzonych w ostatnich 30 dniach i teraz zakończonych "
                "(punkt skrytki przechowania albo nadania; filtr na dacie utworzenia, nie zakończenia)",
    impls={
        "pg": Impl(RANKING_SQL, ranking_sql, plan=sql_plan),
        "mysql": Impl(RANKING_SQL, ranking_sql, plan=sql_plan),
        "mongo": Impl(RANKING_MONGO, ranking_mongo, plan=lambda parameter: Query("orders", pipeline(parameter))),
        "neo4j": Impl(RANKING_CYPHER, ranking_cypher, plan=lambda parameter: Query(RANKING_CYPHER, parameter)),
    },
)]
