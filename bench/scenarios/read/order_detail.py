import json
from operator import itemgetter

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

ORDER = (("order_id", "int"), ("number", "text"), ("type", "text"), ("status", "text"), ("price", "grosze"),
         ("created_at", "ms"))
LEG = (("reservation_id", "int"), ("leg", "text"), ("leg_status", "text"), ("from", "ms"), ("to", "ms"),
       ("lockermat_id", "int"), ("lockermat_name", "text"), ("lockermat_address", "text"))
CODE = (("code_id", "int"), ("purpose", "text"), ("code_status", "text"), ("valid_from", "ms"), ("valid_to", "ms"))
PAYMENT = (("payment_id", "int"), ("kind", "text"), ("payment_status", "text"), ("amount", "grosze"),
           ("payment_created_at", "ms"))
COLUMNS = ORDER + LEG + CODE + PAYMENT
ORDER_KEYS = itemgetter("number", "type", "status", "price", "createdAt")
LEG_KEYS = itemgetter("id", "leg", "status", "from", "to")
LOCKER_KEYS = itemgetter("id", "name", "address")
CODE_KEYS = itemgetter("id", "purpose", "status", "validFrom", "validTo")
PAYMENT_KEYS = itemgetter("id", "kind", "status", "amount", "createdAt")
ELIGIBLE = """
    select o.id_ from order_ o
    where exists (select 1 from reservation_ r where r.order_id_ = o.id_)
      and exists (select 1 from payment_ p where p.order_id_ = o.id_)
    order by 1
"""
DETAIL_SQL = """
select o.id_, o.number_, o.type_, o.status_, o.price_, o.created_at_,
       r.id_, r.leg_, r.status_, r.from_, r.to_, l.id_, l.name_, l.address_,
       a.id_, a.purpose_, a.status_, a.valid_from_, a.valid_to_,
       null, null, null, null, null
from order_ o
join reservation_ r on r.order_id_ = o.id_
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
left join access_code_ a on a.reservation_id_ = r.id_
where o.id_ = %(order)s
union all
select o.id_, o.number_, o.type_, o.status_, o.price_, o.created_at_,
       null, null, null, null, null, null, null, null,
       null, null, null, null, null,
       p.id_, p.kind_, p.status_, p.amount_, p.created_at_
from order_ o
join payment_ p on p.order_id_ = o.id_
where o.id_ = %(order)s
"""
ORDER_PROJECTION = {
    "number": 1, "type": 1, "status": 1, "price": 1, "createdAt": 1,
    "reservations.id": 1, "reservations.leg": 1, "reservations.status": 1, "reservations.from": 1,
    "reservations.to": 1, "reservations.lockermatId": 1,
    "reservations.accessCodes.id": 1, "reservations.accessCodes.purpose": 1, "reservations.accessCodes.status": 1,
    "reservations.accessCodes.validFrom": 1, "reservations.accessCodes.validTo": 1,
    "payments.id": 1, "payments.kind": 1, "payments.status": 1, "payments.amount": 1, "payments.createdAt": 1,
}
LOCKER_PROJECTION = {"name": 1, "address": 1}
DETAIL_MONGO = (f"orders.findOne({{_id: :order}}, {json.dumps(ORDER_PROJECTION)}); "
                f"lockermats.find({{_id: {{$in: <reservations.lockermatId>}}}}, {json.dumps(LOCKER_PROJECTION)})")
DETAIL_CYPHER = """
MATCH (o:Order {id: $order})
RETURN o {.id, .number, .type, .status, .price, .createdAt,
          reservations: [(o)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat) |
                         r {.id, .leg, .status, .from, .to, lockermat: l {.id, .name, .address},
                            accessCodes: [(r)-[:HAS_CODE]->(a:AccessCode) |
                                          a {.id, .purpose, .status, .validFrom, .validTo}]}],
          payments: [(o)-[:HAS_PAYMENT]->(p:Payment) | p {.id, .kind, .status, .amount, .createdAt}]}
"""


def orders(pick):
    ids = [identifier for identifier, in pick.db.execute(ELIGIBLE).fetchall()]
    return [{"order": ids[index]} for index in pick.rng.choice(len(ids), pick.count, replace=False)]


def lines(order_id, order, locker):
    head = [order_id, *ORDER_KEYS(order)]
    found = []
    for leg in order.get("reservations", ()):
        stay = [*LEG_KEYS(leg), *locker(leg)]
        codes = [list(CODE_KEYS(code)) for code in leg.get("accessCodes", ())] or [[None] * len(CODE)]
        found += [head + stay + code + [None] * len(PAYMENT) for code in codes]
    blank = [None] * (len(LEG) + len(CODE))
    return found + [head + blank + list(PAYMENT_KEYS(payment)) for payment in order.get("payments", ())]


def detail_sql(session, parameter):
    return session.fetch(DETAIL_SQL, parameter)


def detail_mongo(session, parameter):
    order = session.handle.orders.find_one({"_id": parameter["order"]}, ORDER_PROJECTION)
    legs = order.get("reservations", ())
    found = session.handle.lockermats.find({"_id": {"$in": [leg["lockermatId"] for leg in legs]}}, LOCKER_PROJECTION)
    lockers = {locker["_id"]: (locker["_id"], locker["name"], locker["address"]) for locker in found}
    return lines(order["_id"], order, lambda leg: lockers[leg["lockermatId"]])


def detail_cypher(session, parameter):
    [[order]] = session.fetch(DETAIL_CYPHER, parameter)
    return lines(order["id"], order, lambda leg: LOCKER_KEYS(leg["lockermat"]))


def sql_plan(parameter):
    return Query(DETAIL_SQL, parameter)


SCENARIOS = [Scenario(
    id="R1", op="R", flags=frozenset({"CX"}), columns=COLUMNS, select=orders,
    description="Szczegóły zamówienia według id: zamówienie, jego rezerwacje z punktem (id, nazwa, adres), "
                "kody dostępu i płatności",
    impls={
        "pg": Impl(DETAIL_SQL, detail_sql, plan=sql_plan),
        "mysql": Impl(DETAIL_SQL, detail_sql, plan=sql_plan),
        "mongo": Impl(DETAIL_MONGO, detail_mongo, plan=lambda parameter: Query("orders", {"_id": parameter["order"]})),
        "neo4j": Impl(DETAIL_CYPHER, detail_cypher, plan=lambda parameter: Query(DETAIL_CYPHER, parameter)),
    },
)]
