from bench.scenarios.explain import Query
from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

UNPAID_PG = "select id_ from order_ where status_ = 'AWAITING_PAYMENT' and payment_deadline_ < %(now)s order by id_"
EXPIRE_PG = """
with expired as (
    update order_ set status_ = 'EXPIRED', closed_at_ = %(now)s
    where id_ = any(%(orders)s) and status_ = 'AWAITING_PAYMENT' and payment_deadline_ < %(now)s
    returning id_
)
update reservation_ r set status_ = 'CANCELLED'
from expired e
where r.order_id_ = e.id_ and r.status_ = 'BOOKED'
"""
UNPAID_MYSQL = """
select id_ from order_ where (case when status_ = 'AWAITING_PAYMENT' then payment_deadline_ end) < %(now)s order by id_
"""
EXPIRE_MYSQL = """
update order_ o
left join reservation_ r on r.order_id_ = o.id_ and r.status_ = 'BOOKED'
set o.status_ = 'EXPIRED', o.closed_at_ = %s, r.status_ = 'CANCELLED'
where o.id_ in ({marks}) and (case when o.status_ = 'AWAITING_PAYMENT' then o.payment_deadline_ end) < %s
"""
BOOKED_SQL = "select id_ from reservation_ where order_id_ in ({marks}) and status_ = 'BOOKED'"
EXPIRE_MONGO = """
orders.find({status: 'AWAITING_PAYMENT', paymentDeadline: {$lt: :now}}, {_id: 1}).sort({_id: 1});
orders.updateMany({_id: {$in: <partia 5000 id>}, status: 'AWAITING_PAYMENT', paymentDeadline: {$lt: :now}},
                  {$set: {status: 'EXPIRED', closedAt: :now, 'reservations.$[leg].status': 'CANCELLED'}},
                  {arrayFilters: [{'leg.status': 'BOOKED'}]})
// jedna transakcja na partię
"""
UNPAID_CYPHER = """
MATCH (o:Order)
WHERE o.status = 'AWAITING_PAYMENT' AND o.paymentDeadline < $now
RETURN o.id ORDER BY o.id
"""
EXPIRE_CYPHER = """
UNWIND $orders AS id
MATCH (o:Order {id: id})
WHERE o.status = 'AWAITING_PAYMENT' AND o.paymentDeadline < $now
SET o.status = 'EXPIRED', o.closedAt = $now
WITH o
MATCH (o)-[:HAS_LEG]->(r:Reservation {status: 'BOOKED'})
SET r.status = 'CANCELLED'
"""
BOOKED_CYPHER = "MATCH (o:Order)-[:HAS_LEG]->(r:Reservation {status: 'BOOKED'}) WHERE o.id IN $orders RETURN r.id"


def deadline(pick):
    return {"now": pick.t0, "batch": pick.config["batch"]}


def unpaid(now):
    return {"status": "AWAITING_PAYMENT", "paymentDeadline": {"$lt": now}}


def marks(values):
    return ", ".join(["%s"] * len(values))


def unpaid_pg(session, params):
    return [row[0] for row in session.fetch(UNPAID_PG, {"now": params["now"]})]


def unpaid_mysql(session, params):
    return [row[0] for row in session.fetch(UNPAID_MYSQL, {"now": params["now"]})]


def unpaid_mongo(session, params):
    return [order["_id"] for order in session.handle.orders.find(unpaid(params["now"]), {"_id": 1}).sort("_id", 1)]


def unpaid_cypher(session, params):
    return [row[0] for row in session.fetch(UNPAID_CYPHER, {"now": params["now"]})]


def legs_sql(session, orders):
    return {"order_": orders,
            "reservation_": [row[0] for row in session.fetch(BOOKED_SQL.format(marks=marks(orders)), orders)]}


def keys_pg(session, params):
    return legs_sql(session, unpaid_pg(session, params))


def keys_mysql(session, params):
    return legs_sql(session, unpaid_mysql(session, params))


def keys_mongo(session, params):
    orders = list(session.handle.orders.find(unpaid(params["now"]), {"reservations.id": 1, "reservations.status": 1}))
    return {"order_": [order["_id"] for order in orders],
            "reservation_": [leg["id"] for order in orders for leg in order.get("reservations", ())
                             if leg["status"] == "BOOKED"]}


def keys_cypher(session, params):
    orders = unpaid_cypher(session, params)
    return {"order_": orders, "reservation_": [row[0] for row in session.fetch(BOOKED_CYPHER, {"orders": orders})]}


def plan_pg(params):
    return Query(UNPAID_PG, {"now": params["now"]})


def plan_mysql(params):
    return Query(UNPAID_MYSQL, {"now": params["now"]})


def plan_mongo(params):
    return Query("orders", unpaid(params["now"]))


def plan_cypher(params):
    return Query(UNPAID_CYPHER, {"now": params["now"]})


def expire_pg(session, params):
    for batch in chunks(unpaid_pg(session, params), params["batch"]):
        with session.transaction() as conn:
            session.driver_counts["reservation_"] += conn.execute(EXPIRE_PG, {"now": params["now"],
                                                                              "orders": batch}).rowcount


def expire_mysql(session, params):
    now = params["now"]
    for batch in chunks(unpaid_mysql(session, params), params["batch"]):
        with session.transaction() as cursor:
            cursor.execute(EXPIRE_MYSQL.format(marks=marks(batch)), [now, *batch, now])
            session.driver_counts["rows"] += cursor.rowcount


def expire_mongo(session, params):
    now = params["now"]
    for batch in chunks(unpaid_mongo(session, params), params["batch"]):
        with session.transaction() as transaction:
            done = session.handle.orders.update_many(
                {"_id": {"$in": batch}} | unpaid(now),
                {"$set": {"status": "EXPIRED", "closedAt": now, "reservations.$[leg].status": "CANCELLED"}},
                array_filters=[{"leg.status": "BOOKED"}], session=transaction)
            session.driver_counts["orders"] += done.modified_count


def expire_cypher(session, params):
    for batch in chunks(unpaid_cypher(session, params), params["batch"]):
        with session.transaction() as tx:
            counters = tx.run(EXPIRE_CYPHER, orders=batch, now=params["now"]).consume().counters
            session.driver_counts["properties"] += counters.properties_set


SCENARIOS = [Scenario(
    id="U3", op="U", select=deadline, flags=frozenset({"BA"}),
    description="Wygaszenie nieopłaconych zamówień po terminie płatności (→ EXPIRED) i anulowanie ich nóg (→ CANCELLED), "
                "partiami po 5000 zamówień",
    impls={
        "pg": Impl(f"{UNPAID_PG};\n{EXPIRE_PG}", expire_pg, keys=keys_pg, plan=plan_pg),
        "mysql": Impl(f"{UNPAID_MYSQL.strip()};\n{EXPIRE_MYSQL}", expire_mysql, keys=keys_mysql, plan=plan_mysql),
        "mongo": Impl(EXPIRE_MONGO, expire_mongo, keys=keys_mongo, plan=plan_mongo),
        "neo4j": Impl(f"{UNPAID_CYPHER.strip()};\n{EXPIRE_CYPHER}", expire_cypher, keys=keys_cypher, plan=plan_cypher),
    },
)]
