import docker
import mysql.connector
from neo4j import GraphDatabase

from bench.gen.cities import ANCHORS
from bench.load.mongo import loader as mongo_loader
from bench.load.mysql import loader as mysql_loader
from bench.load.neo4j import loader as neo4j_loader
from bench.load.pg import loader as pg_loader

from .canonical import BATCH, TABLES, digest

ORIGIN, DESTINATION = (name for name, _, _ in ANCHORS)
REFUNDABLE = ("CHARGE", "EXTENSION", "OVERSTAY")
PG_POINT = "st_asbinary({}, 'NDR')"
PG_DISTANCE = """
    select st_distance(a.location_::geography, b.location_::geography)
    from lockermat_ a, lockermat_ b where a.name_ = %s and b.name_ = %s
"""
PG_DISK = "select pg_database_size(current_database())"
MYSQL_POINT = "st_asbinary({}, 'axis-order=long-lat')"
MYSQL_DISTANCE = """
    select st_distance_sphere(a.location_, b.location_)
    from lockermat_ a join lockermat_ b where a.name_ = %s and b.name_ = %s
"""
MYSQL_DISK = "select sum(file_size) from information_schema.innodb_tablespaces where name like %s"
NEO4J_TABLES = {
    "lockermat_": ("Lockermat", {}),
    "lockermat_opening_hours_": ("OpeningHours", {"lockermat_id_": "(e:Lockermat)-[:HAS_HOURS]->(n)"}),
    "lockermat_cell_": ("Cell", {"lockermat_id_": "(e:Lockermat)-[:HAS_CELL]->(n)"}),
    "tariff_": ("Tariff", {}),
    "customer_": ("Customer", {}),
    "order_": ("Order", {"customer_id_": "(e:Customer)-[:PLACED]->(n)", "tariff_id_": "(n)-[:PRICED_BY]->(e:Tariff)"}),
    "reservation_": ("Reservation", {"order_id_": "(e:Order)-[:HAS_LEG]->(n)", "cell_id_": "(n)-[:IN_CELL]->(e:Cell)"}),
    "shipment_": ("Shipment", {}),
    "access_code_": ("AccessCode", {"reservation_id_": "(e:Reservation)-[:HAS_CODE]->(n)"}),
    "incident_": ("Incident", {
        "cell_id_": "(n)-[:AT_CELL]->(e:Cell)",
        "reservation_id_": "(n)-[:ABOUT]->(e:Reservation)",
        "order_id_": "(n)-[:ABOUT]->(:Reservation)<-[:HAS_LEG]-(e:Order)",
    }),
    "cell_opening_": ("CellOpening", {
        "access_code_id_": "(n)-[:OPENED_WITH]->(e:AccessCode)",
        "incident_id_": "(n)-[:OPENED_FOR]->(e:Incident)",
    }),
    "payment_": ("Payment", {
        "order_id_": "(e:Order)-[:HAS_PAYMENT]->(n)",
        "refund_of_id_": "(n)-[:REFUND_OF]->(e:Payment)",
        "incident_id_": "(n)-[:COMPENSATES]->(e:Incident)",
    }),
    "audit_event_": ("AuditEvent", {}),
}
NEO4J_COPIED = {
    ("order_", "customer_id_"), ("order_", "tariff_id_"), ("incident_", "cell_id_"), ("incident_", "order_id_"),
    ("cell_opening_", "incident_id_"), ("payment_", "refund_of_id_"), ("payment_", "incident_id_"),
}
NEO4J_PROPERTIES = {"shipment_": ("shipmentId",)}
NEO4J_SHIPS_TO = "MATCH (a:Lockermat)-[s:SHIPS_TO]->(b:Lockermat) RETURN s.orderId, a.id, b.id, s.at.epochMillis"
NEO4J_DISTANCE = """
    MATCH (a:Lockermat {name: $origin}), (b:Lockermat {name: $destination})
    RETURN point.distance(a.location, b.location)
"""
NEO4J_STORE = "/data/databases/neo4j"


def camel(column):
    head, *rest = column.removesuffix("_").split("_")
    return head + "".join(part.capitalize() for part in rest)


def build(columns, values, known):
    return [known[name] if name in known else values.get(camel(name)) for name, _ in columns]


def order_type(leg):
    return "STORAGE" if leg == "STORAGE" else "SHIPMENT"


def refundable(payment):
    return payment.get("id") if payment.get("kind") in REFUNDABLE and payment.get("status") == "COMPLETED" else None


def select(columns, point):
    return ", ".join(point.format(name) if kind == "point" else name for name, kind in columns)


def pg_rows(conn, schema):
    for table in TABLES:
        with conn.transaction(), conn.cursor(name="rebuild") as cursor:
            cursor.itersize = BATCH
            cursor.execute(f"select {select(schema[table], PG_POINT)} from {table}")
            for values in cursor:
                yield table, values


def inspect_pg(schema, kinds, problems):
    with pg_loader.connect() as conn:
        digests = digest(pg_rows(conn, schema), kinds)
        [(distance,)] = conn.execute(PG_DISTANCE, (ORIGIN, DESTINATION)).fetchall()
        [(disk,)] = conn.execute(PG_DISK).fetchall()
    return digests, distance, disk


def mysql_rows(conn, schema):
    queries = {table: f"select {select(schema[table], MYSQL_POINT)} from {table}" for table in TABLES}
    queries["changes_new_"] = "select id_, changes_new_ from audit_event_"
    for name, query in queries.items():
        with conn.cursor() as cursor:
            cursor.execute(query)
            while batch := cursor.fetchmany(BATCH):
                for values in batch:
                    yield name, values


def inspect_mysql(schema, kinds, problems):
    with mysql.connector.connect(**mysql_loader.SERVER, database=mysql_loader.DATABASE) as conn:
        digests = digest(mysql_rows(conn, schema), kinds)
        with conn.cursor() as cursor:
            cursor.execute(MYSQL_DISTANCE, (ORIGIN, DESTINATION))
            [(distance,)] = cursor.fetchall()
            cursor.execute(MYSQL_DISK, (f"{mysql_loader.DATABASE}/%",))
            [(disk,)] = cursor.fetchall()
    return digests, distance, disk


def mongo_rows(db, schema):
    for lockermat in db.lockermats.find():
        parent = {"lockermat_id_": lockermat["_id"]}
        yield "lockermat_", build(schema["lockermat_"], lockermat, {"id_": lockermat["_id"]})
        for hours in lockermat.get("openingHours", ()):
            yield "lockermat_opening_hours_", build(schema["lockermat_opening_hours_"], hours, parent)
        for cell in lockermat.get("cells", ()):
            yield "lockermat_cell_", build(schema["lockermat_cell_"], cell, parent)
    for table, collection in (("tariff_", db.tariffs), ("customer_", db.customers), ("audit_event_", db.auditEvents)):
        for document in collection.find():
            yield table, build(schema[table], document, {"id_": document["_id"]})
    for order in db.orders.find():
        yield "order_", build(schema["order_"], order, {"id_": order["_id"]})
        if (shipment := order.get("shipment")) is not None:
            known = {"order_id_": order["_id"], "order_type_": "SHIPMENT"}
            yield "shipment_", build(schema["shipment_"], shipment, known)
            lockers = (shipment.get("originLockermatId"), shipment.get("destinationLockermatId"))
            yield "shipment.lockermatIds", (order["_id"], *lockers)
        for leg in order.get("reservations", ()):
            known = {"order_id_": order["_id"], "order_type_": order_type(leg.get("leg"))}
            yield "reservation_", build(schema["reservation_"], leg, known)
            yield "reservations.lockermatId", (leg.get("id"), leg.get("lockermatId"))
            for code in leg.get("accessCodes", ()):
                yield "access_code_", build(schema["access_code_"], code, {"reservation_id_": leg.get("id")})
                for opening in code.get("openings", ()):
                    known = {"access_code_id_": code.get("id"), "incident_id_": None}
                    yield "cell_opening_", build(schema["cell_opening_"], opening, known)
        for payment in order.get("payments", ()):
            known = {"order_id_": order["_id"], "refundable_id_": refundable(payment)}
            yield "payment_", build(schema["payment_"], payment, known)
    for incident in db.incidents.find():
        yield "incident_", build(schema["incident_"], incident, {"id_": incident["_id"]})
        for opening in incident.get("serviceOpenings", ()):
            known = {"access_code_id_": None, "incident_id_": incident["_id"]}
            yield "cell_opening_", build(schema["cell_opening_"], opening, known)
    for link in db.shipLinks.find():
        yield "shipLinks", (link["_id"], link.get("orderId"), link.get("from"), link.get("to"), link.get("at"))


def inspect_mongo(schema, kinds, problems):
    with mongo_loader.connect() as client:
        db = client[mongo_loader.DATABASE]
        digests = digest(mongo_rows(db, schema), kinds)
        [target] = db.lockermats.find({"name": DESTINATION}, {"location": 1})
        near = {"near": target["location"], "distanceField": "distance", "spherical": True, "query": {"name": ORIGIN}}
        [found] = db.lockermats.aggregate([{"$geoNear": near}])
        disk = db.command("dbStats")["totalSize"]
    return digests, found["distance"], disk


def neo4j_known(table, node):
    if table == "shipment_":
        return {"id_": node.get("shipmentId"), "order_id_": node.get("id"), "order_type_": "SHIPMENT"}
    if table == "reservation_":
        return {"order_type_": order_type(node.get("leg"))}
    if table == "payment_":
        return {"refundable_id_": refundable(node)}
    return {}


def neo4j_projection(table, columns):
    items = [f"{camel(name)}: n.{camel(name)}.epochMillis" if kind == "ms" else f".{camel(name)}" for name, kind in columns]
    return ", ".join(items + [f".{name}" for name in NEO4J_PROPERTIES.get(table, ())])


def neo4j_rows(session, schema, problems):
    for table, (label, edges) in NEO4J_TABLES.items():
        ends = "".join(f", [{pattern} | e.id]" for pattern in edges.values())
        query = f"MATCH (n:{label}) RETURN n {{{neo4j_projection(table, schema[table])}}}{ends}"
        for record in session.run(query):
            node, *found = record.values()
            known = neo4j_known(table, node)
            for (column, pattern), ids in zip(edges.items(), found, strict=True):
                known[column] = ids[0] if ids else None
                copied = (table, column) in NEO4J_COPIED
                if len(ids) > 1 or copied and node.get(camel(column)) != known[column]:
                    property_ = f"{camel(column)} = {node.get(camel(column))}, " if copied else ""
                    problems.append(f"{label} {node.get('id')}: {property_}{pattern} gives {ids}")
            yield table, build(schema[table], node, known)
    for record in session.run(NEO4J_SHIPS_TO):
        yield "SHIPS_TO", record.values()


def neo4j_disk():
    exit_code, output = neo4j_loader.engine(docker.from_env()).exec_run(["du", "-sb", NEO4J_STORE])
    if exit_code:
        raise RuntimeError(output.decode())
    return int(output.split()[0])


def inspect_neo4j(schema, kinds, problems):
    with (GraphDatabase.driver(neo4j_loader.URI, auth=neo4j_loader.AUTH, notifications_min_severity="OFF") as driver,
          driver.session(database="neo4j") as session):
        digests = digest(neo4j_rows(session, schema, problems), kinds)
        distance = session.run(NEO4J_DISTANCE, origin=ORIGIN, destination=DESTINATION).single(strict=True)[0]
    return digests, distance, neo4j_disk()


ENGINES = {"pg": inspect_pg, "mysql": inspect_mysql, "mongo": inspect_mongo, "neo4j": inspect_neo4j}
