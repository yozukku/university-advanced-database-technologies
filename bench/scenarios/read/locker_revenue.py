from datetime import timezone

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("lockermat_id", "int"), ("net", "grosze"))
LEGS = ["STORAGE", "ORIGIN"]
DEBITS = ["REFUND", "COMPENSATION"]
MONTHS = """
    select since, since + interval 1 month
    from (select distinct date_trunc('month', created_at_) as since from payment_
          where status_ = 'COMPLETED' and created_at_ < date_trunc('month', getvariable('benchmark_t0')))
    order by since desc
    limit ?
"""
REVENUE_SQL = """
select c.lockermat_id_, sum(case when p.kind_ in ('REFUND', 'COMPENSATION') then -p.amount_ else p.amount_ end) as net_
from payment_ p
join reservation_ r on r.order_id_ = p.order_id_ and r.leg_ in ('STORAGE', 'ORIGIN')
join lockermat_cell_ c on c.id_ = r.cell_id_
where p.status_ = 'COMPLETED' and p.created_at_ >= %(since)s and p.created_at_ < %(until)s
group by c.lockermat_id_
"""
REVENUE_MONGO = """
orders.aggregate([
  {$match: {payments: {$elemMatch: {status: 'COMPLETED', createdAt: {$gte: :since, $lt: :until}}},
            'payments.createdAt': {$exists: true}}},
  {$unwind: '$payments'},
  {$match: {'payments.status': 'COMPLETED', 'payments.createdAt': {$gte: :since, $lt: :until}}},
  {$unwind: '$reservations'},
  {$match: {'reservations.leg': {$in: ['STORAGE', 'ORIGIN']}}},
  {$group: {_id: '$reservations.lockermatId',
            net: {$sum: {$cond: [{$in: ['$payments.kind', ['REFUND', 'COMPENSATION']]},
                                 {$subtract: [0, '$payments.amount']}, '$payments.amount']}}}}
])
"""
REVENUE_CYPHER = """
MATCH (p:Payment)
WHERE p.createdAt >= $since AND p.createdAt < $until AND p.status = 'COMPLETED'
MATCH (p)<-[:HAS_PAYMENT]-(:Order)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat)
WHERE r.leg IN ['STORAGE', 'ORIGIN']
RETURN l.id AS lockermat, sum(CASE WHEN p.kind IN ['REFUND', 'COMPENSATION'] THEN -p.amount ELSE p.amount END) AS net
"""


def months(pick):
    found = pick.db.execute(MONTHS, [pick.count]).fetchall()
    return [{"since": since.astimezone(timezone.utc), "until": until.astimezone(timezone.utc)}
            for since, until in reversed(found)]


def pipeline(parameter):
    window = {"$gte": parameter["since"], "$lt": parameter["until"]}
    return [
        {"$match": {"payments": {"$elemMatch": {"status": "COMPLETED", "createdAt": window}},
                    "payments.createdAt": {"$exists": True}}},
        {"$unwind": "$payments"},
        {"$match": {"payments.status": "COMPLETED", "payments.createdAt": window}},
        {"$unwind": "$reservations"},
        {"$match": {"reservations.leg": {"$in": LEGS}}},
        {"$group": {"_id": "$reservations.lockermatId",
                    "net": {"$sum": {"$cond": [{"$in": ["$payments.kind", DEBITS]},
                                               {"$subtract": [0, "$payments.amount"]}, "$payments.amount"]}}}},
    ]


def revenue_sql(session, parameter):
    return session.fetch(REVENUE_SQL, parameter)


def revenue_mongo(session, parameter):
    return [(found["_id"], found["net"]) for found in session.handle.orders.aggregate(pipeline(parameter))]


def revenue_cypher(session, parameter):
    return session.fetch(REVENUE_CYPHER, parameter)


def sql_plan(parameter):
    return Query(REVENUE_SQL, parameter)


SCENARIOS = [Scenario(
    id="R6", op="R", flags=frozenset({"CX", "BA", "H1-S"}), columns=COLUMNS, select=months,
    description="Przychód netto każdego punktu w jednym miesiącu (zrealizowane opłaty minus zwroty i rekompensaty, "
                "w groszach), ×12 miesięcy; płatność należy do punktu skrytki przechowania albo, dla przesyłki, "
                "skrytki nadania",
    impls={
        "pg": Impl(REVENUE_SQL, revenue_sql, plan=sql_plan),
        "mysql": Impl(REVENUE_SQL, revenue_sql, plan=sql_plan),
        "mongo": Impl(REVENUE_MONGO, revenue_mongo, plan=lambda parameter: Query("orders", pipeline(parameter))),
        "neo4j": Impl(REVENUE_CYPHER, revenue_cypher, plan=lambda parameter: Query(REVENUE_CYPHER, parameter)),
    },
)]
