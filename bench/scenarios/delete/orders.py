from collections import defaultdict

from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

from .journal import marks

ELIGIBLE = """
    select o.id_ from order_ o
    where exists (select 1 from reservation_ r where r.order_id_ = o.id_)
      and exists (select 1 from payment_ p where p.order_id_ = o.id_)
    order by o.id_
"""
DELETE_PG = (
    ("cell_opening_", "delete from cell_opening_ co using access_code_ a, reservation_ r "
                      "where co.access_code_id_ = a.id_ and a.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s)"),
    ("cell_opening_", "delete from cell_opening_ co using incident_ i, reservation_ r "
                      "where co.incident_id_ = i.id_ and i.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s)"),
    ("access_code_", "delete from access_code_ a using reservation_ r "
                     "where a.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s)"),
    ("payment_", "delete from payment_ where order_id_ = any(%(orders)s)"),
    ("incident_", "delete from incident_ i using reservation_ r where i.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s)"),
    ("reservation_", "delete from reservation_ where order_id_ = any(%(orders)s)"),
    ("shipment_", "delete from shipment_ where order_id_ = any(%(orders)s)"),
    ("order_", "delete from order_ where id_ = any(%(orders)s)"),
)
DELETE_MYSQL = (
    ("cell_opening_", "delete co from cell_opening_ co join access_code_ a on a.id_ = co.access_code_id_ "
                      "join reservation_ r on r.id_ = a.reservation_id_ where r.order_id_ in ({marks})"),
    ("cell_opening_", "delete co from cell_opening_ co join incident_ i on i.id_ = co.incident_id_ "
                      "join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ in ({marks})"),
    ("access_code_", "delete a from access_code_ a join reservation_ r on r.id_ = a.reservation_id_ "
                     "where r.order_id_ in ({marks})"),
    ("payment_", "delete from payment_ where order_id_ in ({marks}) order by refund_of_id_ is null"),
    ("incident_", "delete i from incident_ i join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ in ({marks})"),
    ("reservation_", "delete from reservation_ where order_id_ in ({marks})"),
    ("shipment_", "delete from shipment_ where order_id_ in ({marks})"),
    ("order_", "delete from order_ where id_ in ({marks})"),
)
DELETE_MONGO = ("orders.deleteOne({_id: :order});\nincidents.deleteMany({orderId: {$in: :orders}});\n"
                "shipLinks.deleteMany({orderId: {$in: :orders}})")
SUBTREE_CYPHER = """OPTIONAL MATCH (o)-[:HAS_LEG]->(leg:Reservation)
OPTIONAL MATCH (leg)-[:HAS_CODE]->(code:AccessCode)
OPTIONAL MATCH (code)<-[:OPENED_WITH]-(opening:CellOpening)
OPTIONAL MATCH (leg)<-[:ABOUT]-(incident:Incident)
OPTIONAL MATCH (incident)<-[:OPENED_FOR]-(service:CellOpening)
OPTIONAL MATCH (o)-[:HAS_PAYMENT]->(payment:Payment)
"""
DELETE_CYPHER = """MATCH (o:Order) WHERE o.id IN $orders
OPTIONAL MATCH ()-[link:SHIPS_TO {orderId: o.id}]->()
DELETE link
WITH o
""" + SUBTREE_CYPHER + "DETACH DELETE service, opening, code, payment, incident, leg, o"
OWNED_CYPHER = "MATCH (o:Order) WHERE o.id IN $orders\n" + SUBTREE_CYPHER + """RETURN collect(DISTINCT o.id),
       collect(DISTINCT o.shipmentId), collect(DISTINCT leg.id), collect(DISTINCT code.id),
       collect(DISTINCT opening.id) + collect(DISTINCT service.id), collect(DISTINCT incident.id),
       collect(DISTINCT payment.id)"""
OWNED_TABLES = ("order_", "shipment_", "reservation_", "access_code_", "cell_opening_", "incident_", "payment_")
OWNED_SQL = (
    ("order_", "select id_ from order_ where id_ {orders}"),
    ("shipment_", "select id_ from shipment_ where order_id_ {orders}"),
    ("reservation_", "select id_ from reservation_ where order_id_ {orders}"),
    ("access_code_", "select a.id_ from access_code_ a join reservation_ r on r.id_ = a.reservation_id_ "
                     "where r.order_id_ {orders}"),
    ("cell_opening_", "select co.id_ from cell_opening_ co join access_code_ a on a.id_ = co.access_code_id_ "
                      "join reservation_ r on r.id_ = a.reservation_id_ where r.order_id_ {orders}"),
    ("cell_opening_", "select co.id_ from cell_opening_ co join incident_ i on i.id_ = co.incident_id_ "
                      "join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ {orders}"),
    ("incident_", "select i.id_ from incident_ i join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ {orders}"),
    ("payment_", "select id_ from payment_ where order_id_ {orders}"),
)
LEFT_CYPHER = """RETURN COUNT { MATCH (o:Order) WHERE o.id IN $orders } AS orders,
       COUNT { MATCH (i:Incident) WHERE i.orderId IN $orders } AS incidents,
       COUNT { MATCH ()-[link:SHIPS_TO]->() WHERE link.orderId IN $orders } AS links,
       COUNT { MATCH (n:Reservation) WHERE NOT ()-[:HAS_LEG]->(n) } AS legs,
       COUNT { MATCH (n:AccessCode) WHERE NOT ()-[:HAS_CODE]->(n) } AS codes,
       COUNT { MATCH (n:CellOpening) WHERE NOT (n)-[:OPENED_WITH|OPENED_FOR]->() } AS openings,
       COUNT { MATCH (n:Payment) WHERE NOT ()-[:HAS_PAYMENT]->(n) } AS payments"""
LEFT_NEO4J = ("Order", "Incident", "SHIPS_TO", "Reservation without order", "AccessCode without leg",
              "CellOpening without grant", "Payment without order")


def orders(pick):
    ids = [identifier for identifier, in pick.db.execute(ELIGIBLE).fetchall()]
    chosen = pick.rng.choice(len(ids), pick.count, replace=False)
    return chunks([ids[index] for index in chosen], pick.config["batch"])


def every_order(params):
    return [order for batch in params for order in batch]


def delete_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            for table, statement in DELETE_PG:
                session.driver_counts[table] += conn.execute(statement, {"orders": batch}).rowcount


def delete_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            for table, statement in DELETE_MYSQL:
                cursor.execute(statement.format(marks=marks(batch)), batch)
                session.driver_counts[table] += cursor.rowcount


def delete_mongo(session, params):
    db = session.handle
    for batch in params:
        with session.transaction() as transaction:
            for order in batch:
                session.driver_counts["orders"] += db.orders.delete_one({"_id": order}, session=transaction).deleted_count
            session.driver_counts["incidents"] += db.incidents.delete_many(
                {"orderId": {"$in": batch}}, session=transaction).deleted_count
            session.driver_counts["shipLinks"] += db.shipLinks.delete_many(
                {"orderId": {"$in": batch}}, session=transaction).deleted_count


def delete_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            counters = tx.run(DELETE_CYPHER, orders=batch).consume().counters
            session.driver_counts["nodes"] += counters.nodes_deleted
            session.driver_counts["relationships"] += counters.relationships_deleted


def owned_sql(session, params, match):
    fragment, values = match(every_order(params))
    owned = {table: [] for table in OWNED_TABLES}
    for table, query in OWNED_SQL:
        owned[table] += [row[0] for row in session.fetch(query.format(orders=fragment), values)]
    return owned


def owned_pg(session, params):
    return owned_sql(session, params, lambda found: ("= any(%s)", [found]))


def owned_mysql(session, params):
    return owned_sql(session, params, lambda found: (f"in ({marks(found)})", found))


def owned_mongo(session, params):
    found = every_order(params)
    owned = defaultdict(list)
    for order in session.handle.orders.find({"_id": {"$in": found}}):
        owned["order_"].append(order["_id"])
        if "shipment" in order:
            owned["shipment_"].append(order["shipment"]["id"])
        for leg in order.get("reservations", ()):
            owned["reservation_"].append(leg["id"])
            for code in leg.get("accessCodes", ()):
                owned["access_code_"].append(code["id"])
                owned["cell_opening_"] += [opening["id"] for opening in code.get("openings", ())]
        owned["payment_"] += [payment["id"] for payment in order.get("payments", ())]
    for incident in session.handle.incidents.find({"orderId": {"$in": found}}):
        owned["incident_"].append(incident["_id"])
        owned["cell_opening_"] += [opening["id"] for opening in incident.get("serviceOpenings", ())]
    return {table: owned[table] for table in OWNED_TABLES}


def owned_cypher(session, params):
    return dict(zip(OWNED_TABLES, session.fetch(OWNED_CYPHER, {"orders": every_order(params)})[0], strict=True))


def left_pg(session, params):
    return {table: len(ids) for table, ids in owned_pg(session, params).items()}


def left_mysql(session, params):
    return {table: len(ids) for table, ids in owned_mysql(session, params).items()}


def left_mongo(session, params):
    found = {"$in": every_order(params)}
    db = session.handle
    return {"orders": db.orders.count_documents({"_id": found}),
            "incidents": db.incidents.count_documents({"orderId": found}),
            "shipLinks": db.shipLinks.count_documents({"orderId": found})}


def left_cypher(session, params):
    return dict(zip(LEFT_NEO4J, session.fetch(LEFT_CYPHER, {"orders": every_order(params)})[0], strict=True))


D2 = Scenario(
    id="D2", op="D",
    description="Usunięcie 1000 zamówień ze wszystkimi zależnymi wierszami, od dzieci do rodzica w 7 tabelach, "
                "jedno zamówienie na transakcję",
    select=orders,
    impls={
        "pg": Impl(";\n".join(statement for _, statement in DELETE_PG), delete_pg, keys=owned_pg, after=left_pg),
        "mysql": Impl(";\n".join(statement for _, statement in DELETE_MYSQL), delete_mysql, keys=owned_mysql,
                      after=left_mysql),
        "mongo": Impl(DELETE_MONGO, delete_mongo, keys=owned_mongo, after=left_mongo),
        "neo4j": Impl(DELETE_CYPHER, delete_cypher, keys=owned_cypher, after=left_cypher),
    },
)
SCENARIOS = [D2]
