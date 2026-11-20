from bench.scenarios.explain import Query
from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

COUNT_SQL = "select status_, count(*) from order_ where customer_id_ = %(customer)s group by status_"
COUNT_MONGO = "orders.aggregate([{$match: {customerId: :customer}}, {$group: {_id: '$status', orders: {$sum: 1}}}])"
COUNT_CYPHER = "MATCH (:Customer {id: $customer})-[:PLACED]->(o:Order) RETURN o.status, count(*)"
CANCEL_PG = "update reservation_ set status_ = 'CANCELLED' where order_id_ = any(%s) and leg_ = 'DESTINATION'"
CANCEL_MYSQL = "update reservation_ set status_ = 'CANCELLED' where order_id_ in ({marks}) and leg_ = 'DESTINATION'"
CANCEL_MONGO = ("orders.update_many({_id: {$in: :orders}}, {$set: {'reservations.$[leg].status': 'CANCELLED'}}, "
                "arrayFilters: [{'leg.leg': 'DESTINATION'}])")
CANCEL_CYPHER = ("MATCH (o:Order)-[:HAS_LEG]->(r:Reservation {leg: 'DESTINATION'}) WHERE o.id IN $orders "
                 "SET r.status = 'CANCELLED'")
DESTINATION_PG = "select id_ from reservation_ where order_id_ = any(%s) and leg_ = 'DESTINATION'"
DESTINATION_MYSQL = "select id_ from reservation_ where order_id_ in ({marks}) and leg_ = 'DESTINATION'"
DESTINATION_CYPHER = "MATCH (o:Order)-[:HAS_LEG]->(r:Reservation {leg: 'DESTINATION'}) WHERE o.id IN $orders RETURN r.id"
FIRST_LEG_MONGO = "orders.update_many({_id: {$in: :orders}}, {$set: {'reservations.0.status': 'CANCELLED'}})"
PURGE_PG = "delete from cell_opening_ where id_ = any(%s)"
PURGE_MYSQL = "delete from cell_opening_ where id_ in ({marks})"
PURGE_MONGO = ("orders.update_many({'reservations.accessCodes.openings.id': {$in: :openings}}, "
               "{$pull: {'reservations.$[leg].accessCodes.$[code].openings': {id: {$in: :openings}}}}, "
               "arrayFilters: [{'leg.accessCodes': {$exists: true}}, {'code.openings': {$exists: true}}])")
PURGE_CYPHER = "MATCH (o:CellOpening) WHERE o.id IN $openings DETACH DELETE o"
OLDEST_CYPHER = "MATCH (o:CellOpening)-[:OPENED_WITH]->(:AccessCode) WITH o ORDER BY o.id LIMIT $count DETACH DELETE o"
OLDEST_KEYS = "MATCH (o:CellOpening)-[:OPENED_WITH]->(:AccessCode) RETURN o.id ORDER BY o.id LIMIT $count"


def marks(values):
    return ", ".join(["%s"] * len(values))


def sample(pick, query, name):
    ids = [identifier for identifier, in pick.db.execute(query).fetchall()]
    return [{name: ids[index]} for index in pick.rng.choice(len(ids), pick.count, replace=False)]


def customers(pick):
    return sample(pick, "select distinct customer_id_ from order_ order by 1", "customer")


def count_pipeline(parameter):
    return [{"$match": {"customerId": parameter["customer"]}}, {"$group": {"_id": "$status", "orders": {"$sum": 1}}}]


def count_sql(session, parameter):
    return session.fetch(COUNT_SQL, parameter)


def count_mongo(session, parameter):
    return [(row["_id"], row["orders"]) for row in session.handle.orders.aggregate(count_pipeline(parameter))]


def count_cypher(session, parameter):
    return session.fetch(COUNT_CYPHER, parameter)


COUNT = Scenario(
    id="T1", op="R", description="Próba: liczba zamówień klienta według statusu", flags=frozenset({"BA"}),
    columns=(("status", "text"), ("orders", "int")), ops={"ops": 50, "ops_xs": 10}, select=customers,
    impls={
        "pg": Impl(COUNT_SQL, count_sql, plan=lambda parameter: Query(COUNT_SQL, parameter)),
        "mysql": Impl(COUNT_SQL, count_sql, plan=lambda parameter: Query(COUNT_SQL, parameter)),
        "mongo": Impl(COUNT_MONGO, count_mongo, plan=lambda parameter: Query("orders", count_pipeline(parameter))),
        "neo4j": Impl(COUNT_CYPHER, count_cypher, plan=lambda parameter: Query(COUNT_CYPHER, parameter)),
    },
)


def shipments(pick):
    return chunks(sample(pick, """
        select r.order_id_ from reservation_ r join shipment_ s on s.order_id_ = r.order_id_
        group by 1 having count(*) = 2 and bool_and(r.status_ = 'BOOKED') order by 1
    """, "order"), pick.config["batch"])


def orders(batch):
    return [parameter["order"] for parameter in batch]


def every_order(params):
    return [order for batch in params for order in orders(batch)]


def cancel_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            session.driver_counts["reservation_"] += conn.execute(CANCEL_PG, [orders(batch)]).rowcount


def destination_pg(session, params):
    return {"reservation_": [row[0] for row in session.fetch(DESTINATION_PG, [every_order(params)])]}


def cancel_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.execute(CANCEL_MYSQL.format(marks=marks(batch)), orders(batch))
            session.driver_counts["reservation_"] += cursor.rowcount


def destination_mysql(session, params):
    found = every_order(params)
    return {"reservation_": [row[0] for row in session.fetch(DESTINATION_MYSQL.format(marks=marks(found)), found)]}


def cancel_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            done = session.handle.orders.update_many(
                {"_id": {"$in": orders(batch)}}, {"$set": {"reservations.$[leg].status": "CANCELLED"}},
                array_filters=[{"leg.leg": "DESTINATION"}], session=transaction)
            session.driver_counts["orders"] += done.modified_count


def destination_mongo(session, params):
    documents = session.handle.orders.find({"_id": {"$in": every_order(params)}}, {"reservations.id": 1, "reservations.leg": 1})
    return {"reservation_": [leg["id"] for document in documents for leg in document["reservations"]
                             if leg["leg"] == "DESTINATION"]}


def cancel_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            session.driver_counts["properties"] += tx.run(CANCEL_CYPHER, orders=orders(batch)).consume().counters.properties_set


def destination_cypher(session, params):
    return {"reservation_": [row[0] for row in session.fetch(DESTINATION_CYPHER, {"orders": every_order(params)})]}


def first_leg_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            session.handle.orders.update_many({"_id": {"$in": orders(batch)}},
                                              {"$set": {"reservations.0.status": "CANCELLED"}}, session=transaction)


def first_leg_keys_mongo(session, params):
    documents = session.handle.orders.find({"_id": {"$in": every_order(params)}}, {"reservations.id": 1})
    return {"reservation_": [document["reservations"][0]["id"] for document in documents]}


CANCEL_OPS = {"ops": 100, "ops_xs": 10, "batch": 5}
CANCEL_PG_IMPL = Impl(CANCEL_PG, cancel_pg, keys=destination_pg)
CANCEL = Scenario(
    id="T2", op="U", description="Próba: anulowanie nogi docelowej przesyłek", ops=CANCEL_OPS, select=shipments,
    impls={
        "pg": CANCEL_PG_IMPL,
        "mysql": Impl(CANCEL_MYSQL, cancel_mysql, keys=destination_mysql),
        "mongo": Impl(CANCEL_MONGO, cancel_mongo, keys=destination_mongo),
        "neo4j": Impl(CANCEL_CYPHER, cancel_cypher, keys=destination_cypher),
    },
)
WRONG_LEG = Scenario(
    id="T2-wrong-leg", op="U", description="Próba negatywna: MongoDB anuluje pierwszą nogę zamiast docelowej",
    ops=CANCEL_OPS, select=shipments,
    impls={"pg": CANCEL_PG_IMPL, "mongo": Impl(FIRST_LEG_MONGO, first_leg_mongo, keys=first_leg_keys_mongo)},
)


def openings(pick):
    return chunks(sample(pick, "select id_ from cell_opening_ where access_code_id_ is not null order by 1", "opening"),
                  pick.config["batch"])


def opening_ids(batch):
    return [parameter["opening"] for parameter in batch]


def purge_keys(session, params):
    return {"cell_opening_": [opening for batch in params for opening in opening_ids(batch)]}


def purge_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            session.driver_counts["cell_opening_"] += conn.execute(PURGE_PG, [opening_ids(batch)]).rowcount


def purge_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.execute(PURGE_MYSQL.format(marks=marks(batch)), opening_ids(batch))
            session.driver_counts["cell_opening_"] += cursor.rowcount


def purge_mongo(session, params):
    for batch in params:
        found = opening_ids(batch)
        with session.transaction() as transaction:
            done = session.handle.orders.update_many(
                {"reservations.accessCodes.openings.id": {"$in": found}},
                {"$pull": {"reservations.$[leg].accessCodes.$[code].openings": {"id": {"$in": found}}}},
                array_filters=[{"leg.accessCodes": {"$exists": True}}, {"code.openings": {"$exists": True}}],
                session=transaction)
            session.driver_counts["orders"] += done.modified_count


def purge_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            session.driver_counts["nodes"] += tx.run(PURGE_CYPHER, openings=opening_ids(batch)).consume().counters.nodes_deleted


def oldest_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            tx.run(OLDEST_CYPHER, count=len(batch)).consume()


def oldest_keys_cypher(session, params):
    return {"cell_opening_": [row[0] for row in session.fetch(OLDEST_KEYS, {"count": sum(map(len, params))})]}


PURGE_OPS = {"ops": 200, "ops_xs": 20, "batch": 10}
PURGE_PG_IMPL = Impl(PURGE_PG, purge_pg, keys=purge_keys)
PURGE = Scenario(
    id="T3", op="D", description="Próba: usunięcie wpisów dziennika drzwi według id", ops=PURGE_OPS, select=openings,
    impls={
        "pg": PURGE_PG_IMPL,
        "mysql": Impl(PURGE_MYSQL, purge_mysql, keys=purge_keys),
        "mongo": Impl(PURGE_MONGO, purge_mongo, keys=purge_keys),
        "neo4j": Impl(PURGE_CYPHER, purge_cypher, keys=purge_keys),
    },
)
WRONG_ROWS = Scenario(
    id="T3-wrong-rows", op="D", description="Próba negatywna: Neo4j usuwa tyle samo najstarszych wpisów zamiast wskazanych",
    ops=PURGE_OPS, select=openings,
    impls={"pg": PURGE_PG_IMPL, "neo4j": Impl(OLDEST_CYPHER, oldest_cypher, keys=oldest_keys_cypher)},
)
TRIALS = (COUNT, CANCEL, PURGE)
NEGATIVES = (WRONG_LEG, WRONG_ROWS)
