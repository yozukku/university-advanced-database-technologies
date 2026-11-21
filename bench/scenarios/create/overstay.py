from bson import Int64

from bench.scenarios.explain import Query
from bench.scenarios.params import CHILD, chunks
from bench.scenarios.registry import Impl, Scenario

DAY_MS = 86_400_000
OVERDUE_PG = "select order_id_ from reservation_ where status_ = 'OCCUPIED' and to_ < %(now)s order by order_id_"
CHARGE_PG = f"""
insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, created_at_)
select {CHILD} + o.id_, o.id_, 'OVERSTAY',
       t.overstay_price_per_day_ * ceil(extract(epoch from (%(now)s - r.to_)) / 86400), 'PENDING', 'MOCK', %(now)s
from reservation_ r
join order_ o on o.id_ = r.order_id_
join tariff_ t on t.id_ = o.tariff_id_
where r.order_id_ = any(%(orders)s) and r.status_ = 'OCCUPIED' and r.to_ < %(now)s
"""
OVERDUE_MYSQL = """
select order_id_ from reservation_ where (case when status_ = 'OCCUPIED' then to_ end) < %(now)s order by order_id_
"""
CHARGE_MYSQL = f"""
insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, created_at_)
select {CHILD} + o.id_, o.id_, 'OVERSTAY',
       t.overstay_price_per_day_ * ((timestampdiff(microsecond, r.to_, %s) + 86399999999) div 86400000000),
       'PENDING', 'MOCK', %s
from reservation_ r
join order_ o on o.id_ = r.order_id_
join tariff_ t on t.id_ = o.tariff_id_
where r.order_id_ in ({{marks}}) and (case when r.status_ = 'OCCUPIED' then r.to_ end) < %s
"""
CHARGE_MONGO = """
tariffs.find({}, {overstayPricePerDay: 1});
orders.find({reservations: {$elemMatch: {status: 'OCCUPIED', to: {$lt: :now}}}}, {_id: 1}).sort({_id: 1});
orders.updateMany({_id: {$in: <partia 5000 id>}, reservations: {$elemMatch: {status: 'OCCUPIED', to: {$lt: :now}}}},
                  [{$set: {payments: {$concatArrays: [{$ifNull: ['$payments', []]}, [{$let: {
                      vars: {leg: {$first: {$filter: {input: '$reservations',
                                                      cond: {$and: [{$eq: ['$$this.status', 'OCCUPIED']},
                                                                    {$lt: ['$$this.to', :now]}]}}}}},
                      in: {id: {$add: [10000000000000, '$_id']}, kind: 'OVERSTAY', status: 'PENDING', provider: 'MOCK',
                           createdAt: :now,
                           amount: {$toLong: {$multiply: [{$switch: {branches: [{case: {$eq: ['$tariffId', <id taryfy>]},
                                                                                   then: <stawka za dobę przetrzymania>}, …]}},
                                                          {$ceil: {$divide: [{$subtract: [:now, '$$leg.to']}, 86400000]}}]}}}
                  }}]]}}}])
// jedna transakcja na partię
"""
OVERDUE_CYPHER = """
MATCH (o:Order)-[:HAS_LEG]->(r:Reservation)
WHERE r.status = 'OCCUPIED' AND r.to < $now
RETURN o.id ORDER BY o.id
"""
CHARGE_CYPHER = f"""
UNWIND $orders AS id
MATCH (o:Order {{id: id}})-[:HAS_LEG]->(r:Reservation)
WHERE r.status = 'OCCUPIED' AND r.to < $now
MATCH (o)-[:PRICED_BY]->(t:Tariff)
CREATE (o)-[:HAS_PAYMENT]->(:Payment {{id: {CHILD} + o.id, kind: 'OVERSTAY',
    amount: t.overstayPricePerDay * toInteger(ceil(($now.epochMillis - r.to.epochMillis) / {DAY_MS}.0)),
    status: 'PENDING', provider: 'MOCK', createdAt: $now}})
"""


def cutoff(pick):
    return {"now": pick.t0, "batch": pick.config["batch"]}


def overdue(now):
    return {"reservations": {"$elemMatch": {"status": "OCCUPIED", "to": {"$lt": now}}}}


def overdue_pg(session, params):
    return [row[0] for row in session.fetch(OVERDUE_PG, {"now": params["now"]})]


def overdue_mysql(session, params):
    return [row[0] for row in session.fetch(OVERDUE_MYSQL, {"now": params["now"]})]


def overdue_mongo(session, params):
    return [order["_id"] for order in session.handle.orders.find(overdue(params["now"]), {"_id": 1}).sort("_id", 1)]


def overdue_cypher(session, params):
    return [row[0] for row in session.fetch(OVERDUE_CYPHER, {"now": params["now"]})]


def charges(found):
    return {"payment_": [CHILD + order for order in found]}


def keys_pg(session, params):
    return charges(overdue_pg(session, params))


def keys_mysql(session, params):
    return charges(overdue_mysql(session, params))


def keys_mongo(session, params):
    return charges(overdue_mongo(session, params))


def keys_cypher(session, params):
    return charges(overdue_cypher(session, params))


def plan_pg(params):
    return Query(OVERDUE_PG, {"now": params["now"]})


def plan_mysql(params):
    return Query(OVERDUE_MYSQL, {"now": params["now"]})


def plan_mongo(params):
    return Query("orders", overdue(params["now"]))


def plan_cypher(params):
    return Query(OVERDUE_CYPHER, {"now": params["now"]})


def charge_pg(session, params):
    for batch in chunks(overdue_pg(session, params), params["batch"]):
        with session.transaction() as conn:
            session.driver_counts["payment_"] += conn.execute(CHARGE_PG, {"now": params["now"], "orders": batch}).rowcount


def charge_mysql(session, params):
    now = params["now"]
    for batch in chunks(overdue_mysql(session, params), params["batch"]):
        with session.transaction() as cursor:
            cursor.execute(CHARGE_MYSQL.format(marks=", ".join(["%s"] * len(batch))), [now, now, *batch, now])
            session.driver_counts["payment_"] += cursor.rowcount


def charge_pipeline(rates, now):
    leg = {"$first": {"$filter": {"input": "$reservations", "cond": {
        "$and": [{"$eq": ["$$this.status", "OCCUPIED"]}, {"$lt": ["$$this.to", now]}]}}}}
    rate = {"$switch": {"branches": [{"case": {"$eq": ["$tariffId", tariff]}, "then": price}
                                     for tariff, price in sorted(rates.items())]}}
    days = {"$ceil": {"$divide": [{"$subtract": [now, "$$leg.to"]}, DAY_MS]}}
    charge = {"id": {"$add": [Int64(CHILD), "$_id"]}, "kind": "OVERSTAY", "amount": {"$toLong": {"$multiply": [rate, days]}},
              "status": "PENDING", "provider": "MOCK", "createdAt": now}
    return [{"$set": {"payments": {"$concatArrays": [{"$ifNull": ["$payments", []]},
                                                     [{"$let": {"vars": {"leg": leg}, "in": charge}}]]}}}]


def charge_mongo(session, params):
    db = session.handle
    now = params["now"]
    rates = {tariff["_id"]: tariff["overstayPricePerDay"] for tariff in db.tariffs.find({}, {"overstayPricePerDay": 1})}
    session.driver_counts["tariffs"] += len(rates)
    pipeline = charge_pipeline(rates, now)
    for batch in chunks(overdue_mongo(session, params), params["batch"]):
        with session.transaction() as transaction:
            done = db.orders.update_many({"_id": {"$in": batch}} | overdue(now), pipeline, session=transaction)
            session.driver_counts["orders"] += done.modified_count


def charge_cypher(session, params):
    for batch in chunks(overdue_cypher(session, params), params["batch"]):
        with session.transaction() as tx:
            counters = tx.run(CHARGE_CYPHER, orders=batch, now=params["now"]).consume().counters
            session.driver_counts["nodes"] += counters.nodes_created


SCENARIOS = [Scenario(
    id="C6", op="C", select=cutoff, flags=frozenset({"BA", "H1-I"}),
    description="Naliczenie opłat za przetrzymanie bagażu dla wszystkich zajętych skrytek po terminie: INSERT z zapytania "
                "z ceną z taryfy zamówienia za każdą rozpoczętą dobę, partiami po 5000 zamówień",
    impls={
        "pg": Impl(f"{OVERDUE_PG};\n{CHARGE_PG}", charge_pg, keys=keys_pg, plan=plan_pg),
        "mysql": Impl(f"{OVERDUE_MYSQL.strip()};\n{CHARGE_MYSQL}", charge_mysql, keys=keys_mysql, plan=plan_mysql),
        "mongo": Impl(CHARGE_MONGO, charge_mongo, keys=keys_mongo, plan=plan_mongo),
        "neo4j": Impl(f"{OVERDUE_CYPHER.strip()};\n{CHARGE_CYPHER}", charge_cypher, keys=keys_cypher, plan=plan_cypher),
    },
)]
