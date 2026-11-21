from datetime import timedelta
from hashlib import sha256
from math import ceil
from pathlib import Path

import yaml
from bson import Int64

from bench.check.scenarios import free_cells
from bench.scenarios.params import child_id, chunks, fresh_id
from bench.scenarios.registry import Impl, Scenario

DIGEST_BYTES = 32
PROFILES = Path("profiles.yaml")
LIVE = ["BOOKED", "OCCUPIED"]
PURPOSES = ("DROP_OFF", "PICK_UP")
CUSTOMERS = "select id_ from customer_ order by id_"
BOOK_PG = """
with cell as (
    select c.id_
    from lockermat_cell_ c
    join lockermat_ l on l.id_ = c.lockermat_id_
    where l.id_ = %(locker)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                        and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
    order by c.number_
    limit 1
    for update of c skip locked
), placed as (
    insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_,
                        created_at_)
    select %(order)s, %(number)s, %(customer)s, 'STORAGE', t.size_, t.id_, 'PAID',
           t.storage_price_per_day_ * ceil(extract(epoch from (%(to)s - %(from)s)) / 86400),
           %(now)s + interval '15 minutes', %(now)s
    from tariff_ t cross join cell
    where t.size_ = %(size)s and tstzrange(t.valid_from_, t.valid_to_, '[)') @> %(now)s
    returning id_, size_, price_
), leg as (
    insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
    select %(leg)s, p.id_, p.size_, c.id_, 'STORAGE', %(from)s, %(to)s
    from placed p cross join cell c
    returning id_, cell_id_, from_, to_
), charge as (
    insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
    select %(payment)s, id_, 'CHARGE', price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
    from placed
)
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_, created_at_)
select code.id_, leg.id_, code.purpose_, code.hmac_, leg.from_, leg.to_, %(now)s
from leg cross join unnest(%(code_ids)s::bigint[], %(purposes)s::varchar[], %(hmacs)s::bytea[]) code(id_, purpose_, hmac_)
returning id_
"""
PICK_MYSQL = """
select c.id_
from lockermat_cell_ c
join lockermat_ l on l.id_ = c.lockermat_id_
where l.id_ = %(locker)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                    and r.from_ < %(to)s and r.to_ > %(from)s)
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
order by c.number_
limit 1
for update of c skip locked
"""
PLACE_MYSQL = """
insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_, created_at_)
select %(order)s, %(number)s, %(customer)s, 'STORAGE', t.size_, t.id_, 'PAID',
       t.storage_price_per_day_ * ceil(timestampdiff(second, %(from)s, %(to)s) / 86400),
       %(now)s + interval 15 minute, %(now)s
from tariff_ t
where t.size_ = %(size)s and t.valid_from_ <= %(now)s and (t.valid_to_ is null or t.valid_to_ > %(now)s)
"""
LEG_MYSQL = """
insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
values (%(leg)s, %(order)s, %(size)s, %(cell)s, 'STORAGE', %(from)s, %(to)s)
"""
CHARGE_MYSQL = """
insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
select %(payment)s, o.id_, 'CHARGE', o.price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
from order_ o
where o.id_ = %(order)s
"""
CODES_MYSQL = """
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_, created_at_)
values (%s, %s, %s, %s, %s, %s, %s)
"""
BOOK_MYSQL = ";\n".join(text.strip() for text in (PICK_MYSQL, PLACE_MYSQL, LEG_MYSQL, CHARGE_MYSQL, CODES_MYSQL))
BOOK_MONGO = """
tariffs.findOne({size: :size, validFrom: {$lte: :now}, $or: [{validTo: null}, {validTo: {$gt: :now}}]});
lockermats.findOne({_id: :locker, status: 'ACTIVE'}, {cells: 1});
orders.aggregate([{$match: {$or: [{reservations: {$elemMatch: {cellId: {$in: <skrytki punktu>}, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}},
                                  {reservations: {$elemMatch: {cellId: {$in: <skrytki punktu>}, status: 'OCCUPIED', to: {$lte: :now}}}}]}},
                  {$unwind: '$reservations'},
                  {$match: {$or: [{'reservations.cellId': {$in: <skrytki punktu>}, 'reservations.status': {$in: ['BOOKED', 'OCCUPIED']}, 'reservations.from': {$lt: :to}, 'reservations.to': {$gt: :from}},
                                  {'reservations.cellId': {$in: <skrytki punktu>}, 'reservations.status': 'OCCUPIED', 'reservations.to': {$lte: :now}}]}},
                  {$group: {_id: '$reservations.cellId'}}]);
lockermats.updateOne({_id: :locker, 'cells.id': <pierwsza wolna skrytka według numeru>}, {$inc: {'cells.$.guardSeq': 1}});
orders.findOne({reservations: {$elemMatch: {cellId: <wybrana skrytka>, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}});
orders.insertOne({_id: :order, …, reservations: [{…, accessCodes: [<DROP_OFF>, <PICK_UP>]}], payments: [<CHARGE>]})
// jedna transakcja na rezerwację
"""
BOOK_CYPHER = """
MATCH (:Lockermat {id: $locker, status: 'ACTIVE'})-[:HAS_CELL]->(c:Cell {size: $size, status: 'IN_SERVICE'})
WHERE NOT EXISTS {
    MATCH (c)<-[:IN_CELL]-(r:Reservation)
    WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
       OR (r.status = 'OCCUPIED' AND r.to <= $now)
}
WITH c ORDER BY c.number LIMIT 1
SET c._guard = coalesce(c._guard, 0) + 1
WITH c
WHERE NOT EXISTS {
    MATCH (c)<-[:IN_CELL]-(r:Reservation)
    WHERE r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from
}
MATCH (t:Tariff {size: $size})
WHERE t.validFrom <= $now AND (t.validTo IS NULL OR t.validTo > $now)
MATCH (u:Customer {id: $customer})
WITH c, t, u, t.storagePricePerDay * toInteger(ceil(duration.inSeconds($from, $to).seconds / 86400.0)) AS price
CREATE (u)-[:PLACED]->(o:Order {id: $order, number: $number, customerId: $customer, type: 'STORAGE', size: $size,
                                tariffId: t.id, status: 'PAID', price: price,
                                paymentDeadline: $now + duration({minutes: 15}), createdAt: $now})-[:PRICED_BY]->(t)
CREATE (o)-[:HAS_LEG]->(r:Reservation {id: $leg, size: $size, leg: 'STORAGE', from: $from, to: $to,
                                       status: 'BOOKED'})-[:IN_CELL]->(c)
CREATE (o)-[:HAS_PAYMENT]->(:Payment {id: $payment, kind: 'CHARGE', amount: price, status: 'COMPLETED',
                                      provider: 'MOCK', providerRef: $provider_ref, createdAt: $now, completedAt: $now})
FOREACH (code IN $codes |
    CREATE (r)-[:HAS_CODE]->(:AccessCode {id: code.id, purpose: code.purpose, codeHmac: code.hmac,
                                          validFrom: $from, validTo: $to, status: 'ACTIVE', createdAt: $now}))
RETURN c.id
"""


def bookings(pick):
    seed = yaml.safe_load(PROFILES.read_text())["seed"]
    start = pick.t0 + timedelta(days=pick.config["days_after_t0"])
    cells = sorted(free_cells(pick.db, pick.config))
    customers = [customer for customer, in pick.db.execute(CUSTOMERS).fetchall()]
    found = []
    for n, (cell, buyer) in enumerate(zip(pick.rng.choice(len(cells), pick.count, replace=False),
                                          pick.rng.choice(customers, pick.count, replace=False)), start=1):
        order = fresh_id(n)
        leg = child_id(order, 0)
        codes = [child_id(leg, slot) for slot in range(len(PURPOSES))]
        payment = child_id(order, 0)
        _, locker, size = cells[cell]
        found.append({
            "order": order, "number": f"BAG-{order:010d}", "customer": buyer, "locker": locker, "size": size,
            "from": start, "to": start + timedelta(hours=pick.config["window_hours"]), "now": pick.t0,
            "leg": leg, "payment": payment, "provider_ref": f"MOCK-{payment:010d}", "code_ids": codes,
            "purposes": list(PURPOSES), "hmacs": [digest(seed, code) for code in codes],
        })
    return chunks(found, pick.config["batch"])


def digest(seed, code):
    return sha256(seed.to_bytes(8, "big") + code.to_bytes(8, "big")).digest()


def keys(session, params):
    bookings = [booking for batch in params for booking in batch]
    return {
        "order_": [booking["order"] for booking in bookings],
        "reservation_": [booking["leg"] for booking in bookings],
        "payment_": [booking["payment"] for booking in bookings],
        "access_code_": [code for booking in bookings for code in booking["code_ids"]],
    }


def booked(found, booking):
    if not found:
        raise RuntimeError(f"No free {booking['size']} cell in locker {booking['locker']} for order {booking['order']}")
    return found[0][0]


def book_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            for booking in batch:
                rows = conn.execute(BOOK_PG, booking).fetchall()
                booked(rows, booking)
                session.driver_counts["access_code_"] += len(rows)


def checked(hmac):
    if len(hmac) != DIGEST_BYTES:
        raise ValueError(f"code_hmac_ has {len(hmac)} bytes, BINARY({DIGEST_BYTES}) would pad it")
    return hmac


def book_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            for booking in batch:
                scalars = {key: value for key, value in booking.items() if not isinstance(value, list)}
                cursor.execute(PICK_MYSQL, scalars)
                cell = booked(cursor.fetchall(), booking)
                cursor.execute(PLACE_MYSQL, scalars)
                if cursor.rowcount != 1:
                    raise RuntimeError(f"No tariff for size {booking['size']} at {booking['now']}")
                cursor.execute(LEG_MYSQL, scalars | {"cell": cell})
                cursor.execute(CHARGE_MYSQL, scalars)
                cursor.executemany(CODES_MYSQL, [
                    (code, booking["leg"], purpose, checked(hmac), booking["from"], booking["to"], booking["now"])
                    for code, purpose, hmac in zip(booking["code_ids"], booking["purposes"], booking["hmacs"],
                                                   strict=True)])
                session.driver_counts["access_code_"] += cursor.rowcount


def live(cells, booking):
    return {"cellId": {"$in": cells}, "status": {"$in": LIVE}, "from": {"$lt": booking["to"]},
            "to": {"$gt": booking["from"]}}


def overstayed(cells, booking):
    return {"cellId": {"$in": cells}, "status": "OCCUPIED", "to": {"$lte": booking["now"]}}


def busy_pipeline(cells, booking):
    conditions = (live(cells, booking), overstayed(cells, booking))
    return [
        {"$match": {"$or": [{"reservations": {"$elemMatch": condition}} for condition in conditions]}},
        {"$unwind": "$reservations"},
        {"$match": {"$or": [{f"reservations.{key}": value for key, value in condition.items()}
                            for condition in conditions]}},
        {"$group": {"_id": "$reservations.cellId"}},
    ]


def tariff_filter(booking):
    return {"size": booking["size"], "validFrom": {"$lte": booking["now"]},
            "$or": [{"validTo": None}, {"validTo": {"$gt": booking["now"]}}]}


def order_document(booking, tariff, cell):
    days = ceil((booking["to"] - booking["from"]) / timedelta(days=1))
    price = Int64(tariff["storagePricePerDay"] * days)
    codes = [{"id": Int64(code), "purpose": purpose, "codeHmac": hmac, "validFrom": booking["from"],
              "validTo": booking["to"], "status": "ACTIVE", "createdAt": booking["now"]}
             for code, purpose, hmac in zip(booking["code_ids"], booking["purposes"], booking["hmacs"], strict=True)]
    leg = {"id": Int64(booking["leg"]), "size": booking["size"], "cellId": Int64(cell),
           "lockermatId": Int64(booking["locker"]), "leg": "STORAGE", "from": booking["from"], "to": booking["to"],
           "status": "BOOKED", "accessCodes": codes}
    charge = {"id": Int64(booking["payment"]), "kind": "CHARGE", "amount": price, "status": "COMPLETED",
              "provider": "MOCK", "providerRef": booking["provider_ref"], "createdAt": booking["now"],
              "completedAt": booking["now"]}
    return {"_id": Int64(booking["order"]), "number": booking["number"], "customerId": Int64(booking["customer"]),
            "type": "STORAGE", "size": booking["size"], "tariffId": Int64(tariff["_id"]), "status": "PAID",
            "price": price, "paymentDeadline": booking["now"] + timedelta(minutes=15), "createdAt": booking["now"],
            "reservations": [leg], "payments": [charge]}


def book_mongo(session, params):
    db = session.handle
    for batch in params:
        with session.transaction() as transaction:
            for booking in batch:
                tariff = db.tariffs.find_one(tariff_filter(booking), session=transaction)
                locker = db.lockermats.find_one({"_id": booking["locker"], "status": "ACTIVE"}, {"cells": 1},
                                                session=transaction)
                cells = sorted((cell["number"], cell["id"]) for cell in locker["cells"]
                               if cell["size"] == booking["size"] and cell["status"] == "IN_SERVICE")
                candidates = [cell for _, cell in cells]
                busy = {found["_id"] for found in db.orders.aggregate(busy_pipeline(candidates, booking),
                                                                       session=transaction)}
                cell = booked([(cell,) for cell in candidates if cell not in busy], booking)
                db.lockermats.update_one({"_id": booking["locker"], "cells.id": cell},
                                         {"$inc": {"cells.$.guardSeq": 1}}, session=transaction)
                if db.orders.find_one({"reservations": {"$elemMatch": live([cell], booking)}}, {"_id": 1},
                                      session=transaction):
                    raise RuntimeError(f"Cell {cell} is already booked for order {booking['order']}")
                db.orders.insert_one(order_document(booking, tariff, cell), session=transaction)
                session.driver_counts["orders"] += 1


def book_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            for booking in batch:
                codes = [{"id": code, "purpose": purpose, "hmac": hmac.hex()} for code, purpose, hmac in
                         zip(booking["code_ids"], booking["purposes"], booking["hmacs"], strict=True)]
                found = tx.run(BOOK_CYPHER, booking | {"codes": codes}).values()
                booked(found, booking)
                session.driver_counts["orders"] += len(found)


SCENARIOS = [Scenario(
    id="C3", op="C", select=bookings, flags=frozenset({"BA", "H1-I"}),
    description="Rezerwacja skrytki ×1000: zamówienie, noga, opłata i dwa kody w jednej transakcji, "
                "z wyborem taryfy, wolnej skrytki i kontrolą nakładania rezerwacji",
    impls={
        "pg": Impl(BOOK_PG, book_pg, keys=keys),
        "mysql": Impl(BOOK_MYSQL, book_mysql, keys=keys),
        "mongo": Impl(BOOK_MONGO, book_mongo, keys=keys),
        "neo4j": Impl(BOOK_CYPHER, book_cypher, keys=keys),
    },
)]
