from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

PAID = "select id_ from order_ where status_ = 'PAID' order by id_"
CLOSE_PG = """
update order_ set status_ = 'COMPLETED', closed_at_ = %(now)s
where id_ = any(%(orders)s) and status_ = 'PAID'
"""
CLOSE_MYSQL = """
update order_ set status_ = 'COMPLETED', closed_at_ = %s
where id_ in ({marks}) and status_ = 'PAID'
"""
CLOSE_MONGO = """
orders.updateMany({_id: {$in: :orders}, status: 'PAID'}, {$set: {status: 'COMPLETED', closedAt: :now}})
// jedna transakcja na partię
"""
CLOSE_CYPHER = """
UNWIND $orders AS id
MATCH (o:Order {id: id})
WHERE o.status = 'PAID'
SET o.status = 'COMPLETED', o.closedAt = $now
"""


def paid(pick):
    ids = [order for order, in pick.db.execute(PAID).fetchall()]
    chosen = pick.rng.choice(len(ids), pick.count, replace=False)
    return {"now": pick.t0, "orders": chunks([ids[index] for index in chosen], pick.config["batch"])}


def every_order(session, params):
    return {"order_": [order for batch in params["orders"] for order in batch]}


def close_pg(session, params):
    for batch in params["orders"]:
        with session.transaction() as conn:
            session.driver_counts["order_"] += conn.execute(CLOSE_PG, {"now": params["now"], "orders": batch}).rowcount


def close_mysql(session, params):
    for batch in params["orders"]:
        with session.transaction() as cursor:
            cursor.execute(CLOSE_MYSQL.format(marks=", ".join(["%s"] * len(batch))), [params["now"], *batch])
            session.driver_counts["order_"] += cursor.rowcount


def close_mongo(session, params):
    for batch in params["orders"]:
        with session.transaction() as transaction:
            done = session.handle.orders.update_many({"_id": {"$in": batch}, "status": "PAID"},
                                                     {"$set": {"status": "COMPLETED", "closedAt": params["now"]}},
                                                     session=transaction)
            session.driver_counts["orders"] += done.modified_count


def close_cypher(session, params):
    for batch in params["orders"]:
        with session.transaction() as tx:
            counters = tx.run(CLOSE_CYPHER, orders=batch, now=params["now"]).consume().counters
            session.driver_counts["properties"] += counters.properties_set


SCENARIOS = [Scenario(
    id="U1", op="U", select=paid, flags=frozenset({"BA", "H1-U"}),
    description="Zamknięcie 5000 opłaconych zamówień (PAID → COMPLETED) według id, w transakcjach po 1000 zamówień",
    impls={
        "pg": Impl(CLOSE_PG, close_pg, keys=every_order),
        "mysql": Impl(CLOSE_MYSQL, close_mysql, keys=every_order),
        "mongo": Impl(CLOSE_MONGO, close_mongo, keys=every_order),
        "neo4j": Impl(CLOSE_CYPHER, close_cypher, keys=every_order),
    },
)]
