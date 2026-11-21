from pymongo import UpdateOne

from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

PHONES = 800_000_000
SHIPMENTS = "select order_id_ from shipment_ order by order_id_"
CORRECT_PG = """
update shipment_ s set recipient_phone_ = v.phone
from unnest(%(orders)s::bigint[], %(phones)s::varchar[]) as v (order_id, phone)
where s.order_id_ = v.order_id
"""
CORRECT_MYSQL = """
update shipment_ s
join (values {rows}) as v (order_id, phone) on v.order_id = s.order_id_
set s.recipient_phone_ = v.phone
"""
CORRECT_MONGO = ("orders.bulkWrite([{updateOne: {filter: {_id: :order, shipment: {$exists: true}}, "
                 "update: {$set: {'shipment.recipientPhone': :phone}}}}, …]) in one transaction per batch")
CORRECT_CYPHER = """
UNWIND $rows AS row
MATCH (s:Order:Shipment {id: row.order})
SET s.recipientPhone = row.phone
"""
SHIPMENT_PG = "select id_ from shipment_ where order_id_ = any(%s)"
SHIPMENT_MYSQL = "select id_ from shipment_ where order_id_ in ({marks})"
SHIPMENT_CYPHER = "MATCH (s:Order:Shipment) WHERE s.id IN $orders RETURN s.shipmentId"


def corrections(pick):
    orders = [order for order, in pick.db.execute(SHIPMENTS).fetchall()]
    chosen = pick.rng.choice(len(orders), pick.count, replace=False)
    rows = [{"order": orders[index], "phone": f"+48{PHONES + n}"} for n, index in enumerate(chosen, start=1)]
    return chunks(rows, pick.config["batch"])


def every_order(params):
    return [row["order"] for batch in params for row in batch]


def shipments(rows):
    return {"shipment_": [row[0] for row in rows]}


def keys_pg(session, params):
    return shipments(session.fetch(SHIPMENT_PG, [every_order(params)]))


def keys_mysql(session, params):
    orders = every_order(params)
    return shipments(session.fetch(SHIPMENT_MYSQL.format(marks=", ".join(["%s"] * len(orders))), orders))


def keys_mongo(session, params):
    found = session.handle.orders.find({"_id": {"$in": every_order(params)}}, {"shipment.id": 1})
    return {"shipment_": [order["shipment"]["id"] for order in found]}


def keys_cypher(session, params):
    return shipments(session.fetch(SHIPMENT_CYPHER, {"orders": every_order(params)}))


def correct_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            columns = {"orders": [row["order"] for row in batch], "phones": [row["phone"] for row in batch]}
            session.driver_counts["shipment_"] += conn.execute(CORRECT_PG, columns).rowcount


def correct_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.execute(CORRECT_MYSQL.format(rows=", ".join(["row(%s, %s)"] * len(batch))),
                           [value for row in batch for value in (row["order"], row["phone"])])
            session.driver_counts["shipment_"] += cursor.rowcount


def correct_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            done = session.handle.orders.bulk_write(
                [UpdateOne({"_id": row["order"], "shipment": {"$exists": True}},
                           {"$set": {"shipment.recipientPhone": row["phone"]}}) for row in batch],
                session=transaction)
            session.driver_counts["orders"] += done.modified_count


def correct_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            counters = tx.run(CORRECT_CYPHER, rows=batch).consume().counters
            session.driver_counts["properties"] += counters.properties_set


SCENARIOS = [Scenario(
    id="U5", op="U", select=corrections, flags=frozenset({"BA", "H1-U"}),
    description="Korekta numeru telefonu odbiorcy 5000 przesyłek według id zamówienia, w transakcjach po 1000 przesyłek",
    impls={
        "pg": Impl(CORRECT_PG, correct_pg, keys=keys_pg),
        "mysql": Impl(CORRECT_MYSQL, correct_mysql, keys=keys_mysql),
        "mongo": Impl(CORRECT_MONGO, correct_mongo, keys=keys_mongo),
        "neo4j": Impl(CORRECT_CYPHER, correct_cypher, keys=keys_cypher),
    },
)]
