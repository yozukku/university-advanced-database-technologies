import json

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("order_id", "int"), ("number", "text"), ("type", "text"), ("status", "text"), ("price", "grosze"),
           ("created_at", "ms"))
ELIGIBLE = "select customer_id_ from order_ group by 1 having count(*) >= ? order by 1"
PAGE_SQL = """
select id_, number_, type_, status_, price_, created_at_
from order_
where customer_id_ = %(customer)s
order by created_at_ desc, id_ desc
limit %(limit)s offset %(offset)s
"""
PROJECTION = {"number": 1, "type": 1, "status": 1, "price": 1, "createdAt": 1}
PAGE_MONGO = ("orders.aggregate([{$match: {customerId: :customer}}, {$sort: {createdAt: -1, _id: -1}}, "
              f"{{$skip: :offset}}, {{$limit: :limit}}, {{$project: {json.dumps(PROJECTION)}}}])")
PAGE_CYPHER = """
MATCH (:Customer {id: $customer})-[:PLACED]->(o:Order)
RETURN o.id, o.number, o.type, o.status, o.price, o.createdAt
ORDER BY o.createdAt DESC, o.id DESC
SKIP $offset LIMIT $limit
"""


def customers(pick):
    size = pick.config["page_size"]
    offset = (pick.config["page"] - 1) * size
    ids = [identifier for identifier, in pick.db.execute(ELIGIBLE, [offset + size]).fetchall()]
    return [{"customer": ids[index], "limit": size, "offset": offset}
            for index in pick.rng.choice(len(ids), pick.count)]


def pipeline(parameter):
    return [{"$match": {"customerId": parameter["customer"]}}, {"$sort": {"createdAt": -1, "_id": -1}},
            {"$skip": parameter["offset"]}, {"$limit": parameter["limit"]}, {"$project": PROJECTION}]


def page_sql(session, parameter):
    return session.fetch(PAGE_SQL, parameter)


def page_mongo(session, parameter):
    return [(order["_id"], order["number"], order["type"], order["status"], order["price"], order["createdAt"])
            for order in session.handle.orders.aggregate(pipeline(parameter))]


def page_cypher(session, parameter):
    return session.fetch(PAGE_CYPHER, parameter)


def sql_plan(parameter):
    return Query(PAGE_SQL, parameter)


SCENARIOS = [Scenario(
    id="R2", op="R", columns=COLUMNS, ordered=True, select=customers,
    description="„Moje rezerwacje”: strona 3 (20 wierszy) zamówień klienta od najnowszego",
    impls={
        "pg": Impl(PAGE_SQL, page_sql, plan=sql_plan),
        "mysql": Impl(PAGE_SQL, page_sql, plan=sql_plan),
        "mongo": Impl(PAGE_MONGO, page_mongo, plan=lambda parameter: Query("orders", pipeline(parameter))),
        "neo4j": Impl(PAGE_CYPHER, page_cypher, plan=lambda parameter: Query(PAGE_CYPHER, parameter)),
    },
)]
