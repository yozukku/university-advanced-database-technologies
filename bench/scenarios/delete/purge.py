from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

from . import orders
from .journal import marks, shell

FIRST = [{"$limit": 1}, {"$project": {"_id": 1}}]
CLOSED = ["CANCELLED", "EXPIRED"]

NO_ORDERS_SQL = """select c.id_ from customer_ c
where not exists (select 1 from order_ o where o.customer_id_ = c.id_)
order by c.id_"""
NO_ORDERS_MONGO = [
    {"$lookup": {"from": "orders", "localField": "_id", "foreignField": "customerId", "pipeline": FIRST,
                 "as": "orders"}},
    {"$match": {"orders": {"$size": 0}}},
    {"$project": {"_id": 1}},
]
NO_ORDERS_CYPHER = "MATCH (c:Customer) WHERE COUNT { (c)-[:PLACED]->() } = 0 RETURN c.id ORDER BY c.id"
CUSTOMERS_PG = "delete from customer_ where id_ = any(%s)"
CUSTOMERS_MYSQL = "delete from customer_ where id_ in ({marks})"
CUSTOMERS_CYPHER = "MATCH (c:Customer) WHERE c.id IN $customers DELETE c"

OLD_SQL = "select id_ from order_ where status_ in ('CANCELLED', 'EXPIRED') and created_at_ < %s order by id_"
OLD_CYPHER = "MATCH (o:Order) WHERE o.status IN ['CANCELLED', 'EXPIRED'] AND o.createdAt < $cutoff RETURN o.id ORDER BY o.id"
ORDER_TREES = (("orders", "_id"), ("incidents", "orderId"), ("shipLinks", "orderId"))

UNUSED_SQL = """select l.id_ from lockermat_ l
where not exists (
    select 1 from lockermat_cell_ c
    where c.lockermat_id_ = l.id_
      and (exists (select 1 from reservation_ r where r.cell_id_ = c.id_)
           or exists (select 1 from incident_ i where i.cell_id_ = c.id_))
)
order by l.id_"""
UNUSED_MONGO = [
    {"$project": {"cells.id": 1}},
    {"$lookup": {"from": "orders", "localField": "cells.id", "foreignField": "reservations.cellId", "pipeline": FIRST,
                 "as": "legs"}},
    {"$match": {"legs": {"$size": 0}}},
    {"$lookup": {"from": "incidents", "localField": "cells.id", "foreignField": "cellId", "pipeline": FIRST,
                 "as": "incidents"}},
    {"$match": {"incidents": {"$size": 0}}},
    {"$project": {"_id": 1}},
]
UNUSED_CYPHER = """MATCH (l:Lockermat)
WHERE NOT EXISTS { (l)-[:HAS_CELL]->(:Cell)<-[:IN_CELL|AT_CELL]-() }
RETURN l.id ORDER BY l.id"""
LOCKERS_PG = (
    ("lockermat_opening_hours_", "delete from lockermat_opening_hours_ where lockermat_id_ = any(%s)"),
    ("lockermat_cell_", "delete from lockermat_cell_ where lockermat_id_ = any(%s)"),
    ("lockermat_", "delete from lockermat_ where id_ = any(%s)"),
)
LOCKERS_MYSQL = (
    ("lockermat_opening_hours_", "delete from lockermat_opening_hours_ where lockermat_id_ in ({marks})"),
    ("lockermat_cell_", "delete from lockermat_cell_ where lockermat_id_ in ({marks})"),
    ("lockermat_", "delete from lockermat_ where id_ in ({marks})"),
)
LOCKERS_CYPHER = """MATCH (l:Lockermat) WHERE l.id IN $lockers
OPTIONAL MATCH (l)-[link:HAS_CELL|HAS_HOURS]->(child)
DELETE link, child
WITH DISTINCT l
DELETE l"""
CHILDREN_SQL = (
    ("lockermat_cell_", "select id_ from lockermat_cell_ where lockermat_id_ {lockers}"),
    ("lockermat_opening_hours_", "select id_ from lockermat_opening_hours_ where lockermat_id_ {lockers}"),
)
CHILDREN_CYPHER = """MATCH (l:Lockermat) WHERE l.id IN $lockers
OPTIONAL MATCH (l)-[:HAS_CELL|HAS_HOURS]->(child)
RETURN collect(DISTINCT l.id), collect(CASE WHEN child:Cell THEN child.id END),
       collect(CASE WHEN child:OpeningHours THEN child.id END)"""
LOCKER_TABLES = ("lockermat_", "lockermat_cell_", "lockermat_opening_hours_")

REFERENCES_SQL = (
    ("lockermat_opening_hours_", "lockermat_id_", "lockermat_"),
    ("lockermat_cell_", "lockermat_id_", "lockermat_"),
    ("order_", "customer_id_", "customer_"),
    ("order_", "tariff_id_", "tariff_"),
    ("reservation_", "order_id_", "order_"),
    ("reservation_", "cell_id_", "lockermat_cell_"),
    ("shipment_", "order_id_", "order_"),
    ("access_code_", "reservation_id_", "reservation_"),
    ("incident_", "cell_id_", "lockermat_cell_"),
    ("incident_", "reservation_id_", "reservation_"),
    ("cell_opening_", "access_code_id_", "access_code_"),
    ("cell_opening_", "incident_id_", "incident_"),
    ("payment_", "order_id_", "order_"),
    ("payment_", "refund_of_id_", "payment_"),
    ("payment_", "incident_id_", "incident_"),
)
ORPHANS_SQL = ("select count(*) from {child} c where c.{column} is not null "
               "and not exists (select 1 from {parent} p where p.id_ = c.{column})")
REFERENCES_MONGO = (
    ("orders", "customerId", "customers", "_id"),
    ("orders", "tariffId", "tariffs", "_id"),
    ("orders", "reservations.cellId", "lockermats", "cells.id"),
    ("orders", "reservations.lockermatId", "lockermats", "_id"),
    ("orders", "shipment.originLockermatId", "lockermats", "_id"),
    ("orders", "shipment.destinationLockermatId", "lockermats", "_id"),
    ("incidents", "cellId", "lockermats", "cells.id"),
    ("incidents", "orderId", "orders", "_id"),
    ("incidents", "reservationId", "orders", "reservations.id"),
    ("orders", "payments.incidentId", "incidents", "_id"),
    ("shipLinks", "orderId", "orders", "_id"),
    ("shipLinks", "from", "lockermats", "_id"),
    ("shipLinks", "to", "lockermats", "_id"),
)
ORPHANS_CYPHER = """RETURN COUNT { MATCH (n:OpeningHours) WHERE NOT (:Lockermat)-[:HAS_HOURS]->(n) },
       COUNT { MATCH (n:Cell) WHERE NOT (:Lockermat)-[:HAS_CELL]->(n) },
       COUNT { MATCH (n:Order) WHERE NOT (:Customer)-[:PLACED]->(n) OR NOT (n)-[:PRICED_BY]->(:Tariff) },
       COUNT { MATCH (n:Reservation) WHERE NOT (:Order)-[:HAS_LEG]->(n) OR NOT (n)-[:IN_CELL]->(:Cell) },
       COUNT { MATCH (n:AccessCode) WHERE NOT (:Reservation)-[:HAS_CODE]->(n) },
       COUNT { MATCH (n:Incident) WHERE NOT (n)-[:AT_CELL]->(:Cell)
                                     OR (n.orderId IS NOT NULL AND NOT (n)-[:ABOUT]->(:Reservation)) },
       COUNT { MATCH (n:CellOpening) WHERE NOT (n)-[:OPENED_WITH]->(:AccessCode) AND NOT (n)-[:OPENED_FOR]->(:Incident) },
       COUNT { MATCH (n:Payment) WHERE NOT (:Order)-[:HAS_PAYMENT]->(n)
                                    OR (n.incidentId IS NOT NULL AND NOT (n)-[:COMPENSATES]->(:Incident)) },
       COUNT { MATCH ()-[link:SHIPS_TO]->() WHERE NOT EXISTS { MATCH (o:Order {id: link.orderId}) } }"""
ORPHANS_NEO4J = ("OpeningHours without Lockermat", "Cell without Lockermat", "Order without Customer or Tariff",
                 "Reservation without Order or Cell", "AccessCode without Reservation",
                 "Incident without Cell or Reservation", "CellOpening without grant",
                 "Payment without Order or Incident", "SHIPS_TO without Order")


def column(session, text, params=None):
    return [row[0] for row in session.fetch(text, params)]


def batch_only(pick):
    return {"batch": pick.config["batch"]}


def old_orders(pick):
    return {"cutoff": pick.t0.replace(year=pick.t0.year - pick.config["cutoff_years"]), "batch": pick.config["batch"]}


def pluck(value, path):
    if isinstance(value, list):
        return [found for item in value for found in pluck(item, path)]
    if not path:
        return [value]
    return pluck(value[path[0]], path[1:]) if path[0] in value else []


def values(db, collection, path):
    return {found for document in db[collection].find({path: {"$exists": True}}, {path: 1})
            for found in pluck(document, path.split("."))}


def orphans_sql(session):
    return {f"{child}.{name}": session.fetch(ORPHANS_SQL.format(child=child, column=name, parent=parent))[0][0]
            for child, name, parent in REFERENCES_SQL}


def orphans_mongo(session):
    db = session.handle
    return {f"{child}.{path}": len(values(db, child, path) - values(db, parent, key))
            for child, path, parent, key in REFERENCES_MONGO}


def orphans_cypher(session):
    return dict(zip(ORPHANS_NEO4J, session.fetch(ORPHANS_CYPHER)[0], strict=True))


def no_orders_sql(session, params):
    return column(session, NO_ORDERS_SQL)


def no_orders_mongo(session, params):
    return sorted(found["_id"] for found in session.handle.customers.aggregate(NO_ORDERS_MONGO))


def no_orders_cypher(session, params):
    return column(session, NO_ORDERS_CYPHER)


def customers_pg(session, params):
    for batch in chunks(no_orders_sql(session, params), params["batch"]):
        with session.transaction() as conn:
            session.driver_counts["customer_"] += conn.execute(CUSTOMERS_PG, [batch]).rowcount


def customers_mysql(session, params):
    for batch in chunks(no_orders_sql(session, params), params["batch"]):
        with session.transaction() as cursor:
            cursor.execute(CUSTOMERS_MYSQL.format(marks=marks(batch)), batch)
            session.driver_counts["customer_"] += cursor.rowcount


def customers_mongo(session, params):
    for batch in chunks(no_orders_mongo(session, params), params["batch"]):
        with session.transaction() as transaction:
            session.driver_counts["customers"] += session.handle.customers.delete_many(
                {"_id": {"$in": batch}}, session=transaction).deleted_count


def customers_cypher(session, params):
    for batch in chunks(no_orders_cypher(session, params), params["batch"]):
        with session.transaction() as tx:
            session.driver_counts["nodes"] += tx.run(CUSTOMERS_CYPHER, customers=batch).consume().counters.nodes_deleted


def no_orders_keys_sql(session, params):
    return {"customer_": no_orders_sql(session, params)}


def no_orders_keys_mongo(session, params):
    return {"customer_": no_orders_mongo(session, params)}


def no_orders_keys_cypher(session, params):
    return {"customer_": no_orders_cypher(session, params)}


def old_sql(session, params):
    return column(session, OLD_SQL, [params["cutoff"]])


def old_filter(cutoff):
    return {"status": {"$in": CLOSED}, "createdAt": {"$lt": cutoff}}


def old_mongo(session, params):
    return sorted(found["_id"] for found in session.handle.orders.find(old_filter(params["cutoff"]), {"_id": 1}))


def old_cypher(session, params):
    return column(session, OLD_CYPHER, {"cutoff": params["cutoff"]})


def old_orders_pg(session, params):
    orders.delete_pg(session, chunks(old_sql(session, params), params["batch"]))


def old_orders_mysql(session, params):
    orders.delete_mysql(session, chunks(old_sql(session, params), params["batch"]))


def old_orders_mongo(session, params):
    db = session.handle
    for batch in chunks(old_mongo(session, params), params["batch"]):
        with session.transaction() as transaction:
            for name, field in ORDER_TREES:
                session.driver_counts[name] += db[name].delete_many({field: {"$in": batch}},
                                                                    session=transaction).deleted_count


def old_orders_cypher(session, params):
    orders.delete_cypher(session, chunks(old_cypher(session, params), params["batch"]))


def old_keys_pg(session, params):
    return orders.owned_pg(session, [old_sql(session, params)])


def old_keys_mysql(session, params):
    return orders.owned_mysql(session, [old_sql(session, params)])


def old_keys_mongo(session, params):
    return orders.owned_mongo(session, [old_mongo(session, params)])


def old_keys_cypher(session, params):
    return orders.owned_cypher(session, [old_cypher(session, params)])


def unused_sql(session, params):
    return column(session, UNUSED_SQL)


def unused_mongo(session, params):
    return sorted(found["_id"] for found in session.handle.lockermats.aggregate(UNUSED_MONGO))


def unused_cypher(session, params):
    return column(session, UNUSED_CYPHER)


def lockers_pg(session, params):
    for batch in chunks(unused_sql(session, params), params["batch"]):
        with session.transaction() as conn:
            for table, statement in LOCKERS_PG:
                session.driver_counts[table] += conn.execute(statement, [batch]).rowcount


def lockers_mysql(session, params):
    for batch in chunks(unused_sql(session, params), params["batch"]):
        with session.transaction() as cursor:
            for table, statement in LOCKERS_MYSQL:
                cursor.execute(statement.format(marks=marks(batch)), batch)
                session.driver_counts[table] += cursor.rowcount


def lockers_mongo(session, params):
    for batch in chunks(unused_mongo(session, params), params["batch"]):
        with session.transaction() as transaction:
            session.driver_counts["lockermats"] += session.handle.lockermats.delete_many(
                {"_id": {"$in": batch}}, session=transaction).deleted_count


def lockers_cypher(session, params):
    for batch in chunks(unused_cypher(session, params), params["batch"]):
        with session.transaction() as tx:
            session.driver_counts["nodes"] += tx.run(LOCKERS_CYPHER, lockers=batch).consume().counters.nodes_deleted


def unused_keys_sql(session, lockers, fragment, bound):
    return {"lockermat_": lockers} | {table: column(session, query.format(lockers=fragment), bound)
                                      for table, query in CHILDREN_SQL}


def unused_keys_pg(session, params):
    lockers = unused_sql(session, params)
    return unused_keys_sql(session, lockers, "= any(%s)", [lockers])


def unused_keys_mysql(session, params):
    lockers = unused_sql(session, params)
    return unused_keys_sql(session, lockers, f"in ({marks(lockers)})", lockers)


def unused_keys_mongo(session, params):
    found = {table: [] for table in LOCKER_TABLES}
    for locker in session.handle.lockermats.find({"_id": {"$in": unused_mongo(session, params)}},
                                                 {"cells.id": 1, "openingHours.id": 1}):
        found["lockermat_"].append(locker["_id"])
        found["lockermat_cell_"] += [cell["id"] for cell in locker.get("cells", ())]
        found["lockermat_opening_hours_"] += [hours["id"] for hours in locker.get("openingHours", ())]
    return found


def unused_keys_cypher(session, params):
    return dict(zip(LOCKER_TABLES, session.fetch(CHILDREN_CYPHER, {"lockers": unused_cypher(session, params)})[0],
                    strict=True))


def remaining(discover, orphans):
    return lambda session, params: {"left": len(discover(session, params))} | orphans(session)


def mongo_text(collection, method, discovery, deletes):
    return ";\n".join([shell(collection, method, *discovery),
                       *(shell(name, "deleteMany", {field: {"$in": ":batch"}}) for name, field in deletes)])


def sql_text(discovery, deletes):
    return ";\n".join([discovery, *(statement for _, statement in deletes)])


D4 = Scenario(
    id="D4", op="D",
    description="Usunięcie klientów bez żadnego zamówienia (antyzłączenie), partiami po 5000 klientów",
    select=batch_only,
    impls={
        "pg": Impl(sql_text(NO_ORDERS_SQL, [("customer_", CUSTOMERS_PG)]), customers_pg, keys=no_orders_keys_sql,
                   after=remaining(no_orders_sql, orphans_sql)),
        "mysql": Impl(sql_text(NO_ORDERS_SQL, [("customer_", CUSTOMERS_MYSQL)]), customers_mysql, keys=no_orders_keys_sql,
                      after=remaining(no_orders_sql, orphans_sql)),
        "mongo": Impl(mongo_text("customers", "aggregate", [NO_ORDERS_MONGO], [("customers", "_id")]),
                      customers_mongo, keys=no_orders_keys_mongo, after=remaining(no_orders_mongo, orphans_mongo)),
        "neo4j": Impl(f"{NO_ORDERS_CYPHER};\n{CUSTOMERS_CYPHER}", customers_cypher, keys=no_orders_keys_cypher,
                      after=remaining(no_orders_cypher, orphans_cypher)),
    },
)
D5 = Scenario(
    id="D5", op="D",
    description="Usunięcie anulowanych i wygasłych zamówień starszych niż rok przed T0 ze wszystkimi zależnymi "
                "wierszami, partiami po 5000 zamówień",
    select=old_orders,
    impls={
        "pg": Impl(sql_text(OLD_SQL, orders.DELETE_PG), old_orders_pg, keys=old_keys_pg,
                   after=remaining(old_sql, orphans_sql)),
        "mysql": Impl(sql_text(OLD_SQL, orders.DELETE_MYSQL), old_orders_mysql, keys=old_keys_mysql,
                      after=remaining(old_sql, orphans_sql)),
        "mongo": Impl(mongo_text("orders", "find", [old_filter(":cutoff"), {"_id": 1}], ORDER_TREES),
                      old_orders_mongo, keys=old_keys_mongo, after=remaining(old_mongo, orphans_mongo)),
        "neo4j": Impl(f"{OLD_CYPHER};\n{orders.DELETE_CYPHER}", old_orders_cypher, keys=old_keys_cypher,
                      after=remaining(old_cypher, orphans_cypher)),
    },
)
D6 = Scenario(
    id="D6", op="D",
    description="Usunięcie nieużywanych punktów razem ze skrytkami i godzinami otwarcia po sprawdzeniu, "
                "że żadna rezerwacja ani zgłoszenie nie wskazuje ich skrytek, partiami po 5000 punktów",
    select=batch_only,
    impls={
        "pg": Impl(sql_text(UNUSED_SQL, LOCKERS_PG), lockers_pg, keys=unused_keys_pg,
                   after=remaining(unused_sql, orphans_sql)),
        "mysql": Impl(sql_text(UNUSED_SQL, LOCKERS_MYSQL), lockers_mysql, keys=unused_keys_mysql,
                      after=remaining(unused_sql, orphans_sql)),
        "mongo": Impl(mongo_text("lockermats", "aggregate", [UNUSED_MONGO], [("lockermats", "_id")]),
                      lockers_mongo, keys=unused_keys_mongo, after=remaining(unused_mongo, orphans_mongo)),
        "neo4j": Impl(f"{UNUSED_CYPHER};\n{LOCKERS_CYPHER}", lockers_cypher, keys=unused_keys_cypher,
                      after=remaining(unused_cypher, orphans_cypher)),
    },
)
SCENARIOS = [D4, D5, D6]
