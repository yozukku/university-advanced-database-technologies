from datetime import timedelta

import yaml
from bson import Int64

from bench.check.scenarios import free_cells
from bench.check.verify.canonical import milliseconds
from bench.scenarios.create.booking import (CHARGE_MYSQL, CUSTOMERS, PICK_MYSQL, PROFILES, PURPOSES, busy_pipeline,
                                            checked, digest, live, tariff_filter)
from bench.scenarios.params import child_id, chunks, fresh_id
from bench.scenarios.registry import Impl, Scenario

ROUTE = (("ORIGIN", "origin"), ("DESTINATION", "destination"))
CODES = tuple((leg, purpose) for leg, _ in ROUTE for purpose in PURPOSES)
RECIPIENTS = "select distinct recipient_name_, recipient_phone_ from shipment_ order by all"
PICK_PG = """
    select c.id_
    from lockermat_cell_ c
    join lockermat_ l on l.id_ = c.lockermat_id_
    where l.id_ = %({locker})s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                        and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
    order by c.number_
    limit 1
    for update of c skip locked
"""
SHIP_PG = f"""
with origin as ({PICK_PG.format(locker="origin")}), destination as ({PICK_PG.format(locker="destination")}),
placed as (
    insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_,
                        created_at_)
    select %(order)s, %(number)s, %(customer)s, 'SHIPMENT', t.size_, t.id_, 'PAID', t.shipment_price_,
           %(now)s + interval '15 minutes', %(now)s
    from tariff_ t cross join origin cross join destination
    where t.size_ = %(size)s and tstzrange(t.valid_from_, t.valid_to_, '[)') @> %(now)s
    returning id_, size_, price_
), parcel as (
    insert into shipment_ (id_, order_id_, recipient_name_, recipient_phone_, declared_value_)
    select %(shipment)s, id_, %(recipient_name)s, %(recipient_phone)s, %(declared)s::numeric / 100
    from placed
), legs as (
    insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
    select leg.id_, p.id_, p.size_, leg.cell_id_, leg.leg_, %(from)s, %(to)s
    from placed p
    cross join (select %(origin_leg)s::bigint, id_, 'ORIGIN' from origin
                union all
                select %(destination_leg)s::bigint, id_, 'DESTINATION' from destination) leg(id_, cell_id_, leg_)
    returning id_, leg_, from_, to_
), charge as (
    insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
    select %(payment)s, id_, 'CHARGE', price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
    from placed
)
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, sent_to_phone_, valid_from_, valid_to_, created_at_)
select code.id_, legs.id_, code.purpose_, code.hmac_, code.phone_, legs.from_, legs.to_, %(now)s
from legs
join unnest(%(code_ids)s::bigint[], %(code_legs)s::varchar[], %(purposes)s::varchar[], %(hmacs)s::bytea[],
            %(phones)s::varchar[]) code(id_, leg_, purpose_, hmac_, phone_) on code.leg_ = legs.leg_
returning id_
"""
PLACE_MYSQL = """
insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_, created_at_)
select %(order)s, %(number)s, %(customer)s, 'SHIPMENT', t.size_, t.id_, 'PAID', t.shipment_price_,
       %(now)s + interval 15 minute, %(now)s
from tariff_ t
where t.size_ = %(size)s and t.valid_from_ <= %(now)s and (t.valid_to_ is null or t.valid_to_ > %(now)s)
"""
PARCEL_MYSQL = """
insert into shipment_ (id_, order_id_, recipient_name_, recipient_phone_, declared_value_)
values (%(shipment)s, %(order)s, %(recipient_name)s, %(recipient_phone)s, %(declared)s / 100)
"""
LEGS_MYSQL = """
insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
values (%(origin_leg)s, %(order)s, %(size)s, %(origin_cell)s, 'ORIGIN', %(from)s, %(to)s),
       (%(destination_leg)s, %(order)s, %(size)s, %(destination_cell)s, 'DESTINATION', %(from)s, %(to)s)
"""
CODES_MYSQL = """
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, sent_to_phone_, valid_from_, valid_to_, created_at_)
values (%s, %s, %s, %s, %s, %s, %s, %s)
"""
SHIP_MYSQL = ";\n".join(text.strip() for text in (
    PICK_MYSQL.replace("%(locker)s", "%(origin)s"), PICK_MYSQL.replace("%(locker)s", "%(destination)s"),
    PLACE_MYSQL, PARCEL_MYSQL, LEGS_MYSQL, CHARGE_MYSQL, CODES_MYSQL))
SHIP_MONGO = """
tariffs.findOne({size: :size, validFrom: {$lte: :now}, $or: [{validTo: null}, {validTo: {$gt: :now}}]});
lockermats.find({_id: {$in: [:origin, :destination]}, status: 'ACTIVE'}, {cells: 1});
orders.aggregate([{$match: {$or: [{reservations: {$elemMatch: {cellId: {$in: <cells of both lockers>}, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}},
                                  {reservations: {$elemMatch: {cellId: {$in: <cells of both lockers>}, status: 'OCCUPIED', to: {$lte: :now}}}}]}},
                  {$unwind: '$reservations'}, {$match: <the same two conditions on reservations>},
                  {$group: {_id: '$reservations.cellId'}}]);
lockermats.updateOne({_id: :origin, 'cells.id': <first free origin cell by number>}, {$inc: {'cells.$.guardSeq': 1}});
lockermats.updateOne({_id: :destination, 'cells.id': <first free destination cell by number>}, {$inc: {'cells.$.guardSeq': 1}});
orders.findOne({reservations: {$elemMatch: {cellId: {$in: <both cells>}, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}});
orders.insertOne({_id: :order, …, shipment: {…, originLockermatId, destinationLockermatId},
                  reservations: [{leg: 'ORIGIN', lockermatId, accessCodes: [<DROP_OFF>, <PICK_UP>]},
                                 {leg: 'DESTINATION', lockermatId, accessCodes: [<DROP_OFF>, <PICK_UP sent to the recipient>]}],
                  payments: [<CHARGE>]});
shipLinks.insertOne({_id: :order, orderId: :order, from: :origin, to: :destination, at: :now})
in one transaction per shipment
"""
FREE_CYPHER = """
    WHERE NOT EXISTS {{
        MATCH ({cell})<-[:IN_CELL]-(r:Reservation)
        WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
           OR (r.status = 'OCCUPIED' AND r.to <= $now)
    }}
"""
LIVE_CYPHER = """
    NOT EXISTS {{
        MATCH ({cell})<-[:IN_CELL]-(r:Reservation)
        WHERE r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from
    }}
"""
CODE_CYPHER = """
FOREACH (code IN [item IN $codes WHERE item.leg = '{leg}'] |
    CREATE ({leg_node})-[:HAS_CODE]->(:AccessCode {{id: code.id, purpose: code.purpose, codeHmac: code.hmac,
                                                  sentToPhone: code.phone, validFrom: $from, validTo: $to,
                                                  status: 'ACTIVE', createdAt: $now}}))
"""
SHIP_CYPHER = f"""
MATCH (ol:Lockermat {{id: $origin, status: 'ACTIVE'}})-[:HAS_CELL]->(oc:Cell {{size: $size, status: 'IN_SERVICE'}})
{FREE_CYPHER.format(cell="oc")}
WITH ol, oc ORDER BY oc.number LIMIT 1
MATCH (dl:Lockermat {{id: $destination, status: 'ACTIVE'}})-[:HAS_CELL]->(dc:Cell {{size: $size, status: 'IN_SERVICE'}})
{FREE_CYPHER.format(cell="dc")}
WITH ol, oc, dl, dc ORDER BY dc.number LIMIT 1
SET oc._guard = coalesce(oc._guard, 0) + 1, dc._guard = coalesce(dc._guard, 0) + 1
WITH ol, oc, dl, dc
WHERE {LIVE_CYPHER.format(cell="oc")} AND {LIVE_CYPHER.format(cell="dc")}
MATCH (t:Tariff {{size: $size}})
WHERE t.validFrom <= $now AND (t.validTo IS NULL OR t.validTo > $now)
MATCH (u:Customer {{id: $customer}})
CREATE (u)-[:PLACED]->(o:Order:Shipment {{id: $order, number: $number, customerId: $customer, type: 'SHIPMENT',
                                         size: $size, tariffId: t.id, status: 'PAID', price: t.shipmentPrice,
                                         paymentDeadline: $now + duration({{minutes: 15}}), createdAt: $now,
                                         shipmentId: $shipment, recipientName: $recipient_name,
                                         recipientPhone: $recipient_phone, declaredValue: $declared}})-[:PRICED_BY]->(t)
CREATE (o)-[:HAS_LEG]->(ro:Reservation {{id: $origin_leg, size: $size, leg: 'ORIGIN', from: $from, to: $to,
                                        status: 'BOOKED'}})-[:IN_CELL]->(oc)
CREATE (o)-[:HAS_LEG]->(rd:Reservation {{id: $destination_leg, size: $size, leg: 'DESTINATION', from: $from, to: $to,
                                        status: 'BOOKED'}})-[:IN_CELL]->(dc)
CREATE (o)-[:HAS_PAYMENT]->(:Payment {{id: $payment, kind: 'CHARGE', amount: t.shipmentPrice, status: 'COMPLETED',
                                      provider: 'MOCK', providerRef: $provider_ref, createdAt: $now,
                                      completedAt: $now}})
CREATE (ol)-[:SHIPS_TO {{orderId: $order, at: $now}}]->(dl)
{CODE_CYPHER.format(leg="ORIGIN", leg_node="ro")}
{CODE_CYPHER.format(leg="DESTINATION", leg_node="rd")}
RETURN oc.id, dc.id
"""
LINKS_CYPHER = """
MATCH (a:Lockermat)-[s:SHIPS_TO]->(b:Lockermat)
WHERE s.orderId IN $orders
RETURN s.orderId, a.id, b.id, s.at.epochMillis ORDER BY s.orderId
"""


def routes(cells):
    found = []
    for size in sorted({size for _, _, size in cells}):
        group = sorted((locker, cell) for cell, locker, cell_size in cells if cell_size == size)
        half = len(group) // 2
        found += [(size, origin, destination) for (origin, _), (destination, _) in zip(group[:half], group[half:])
                  if origin != destination]
    return found


def shipments(pick):
    seed = yaml.safe_load(PROFILES.read_text())["seed"]
    start = pick.t0 + timedelta(days=pick.config["days_after_t0"])
    paths = routes(free_cells(pick.db, pick.config))
    customers = [customer for customer, in pick.db.execute(CUSTOMERS).fetchall()]
    recipients = pick.db.execute(RECIPIENTS).fetchall()
    found = []
    for n, (path, buyer, recipient, declared, flip) in enumerate(zip(
            pick.rng.choice(len(paths), pick.count, replace=False),
            pick.rng.choice(customers, pick.count, replace=False),
            pick.rng.choice(len(recipients), pick.count),
            pick.rng.integers(5, 201, pick.count) * 1000,
            pick.rng.integers(0, 2, pick.count)), start=1):
        size, origin, destination = paths[path]
        if flip:
            origin, destination = destination, origin
        order = fresh_id(n)
        codes = [child_id(order, slot) for slot in range(len(CODES))]
        name, phone = recipients[recipient]
        found.append({
            "order": order, "number": f"BAG-{order:010d}", "customer": buyer, "size": size,
            "origin": origin, "destination": destination, "now": pick.t0,
            "from": start, "to": start + timedelta(hours=pick.config["window_hours"]),
            "shipment": child_id(order, 0), "recipient_name": name, "recipient_phone": phone, "declared": declared,
            "origin_leg": child_id(order, 0), "destination_leg": child_id(order, 1),
            "payment": child_id(order, 0), "provider_ref": f"MOCK-{child_id(order, 0):010d}",
            "code_ids": codes, "code_legs": [leg for leg, _ in CODES], "purposes": [purpose for _, purpose in CODES],
            "hmacs": [digest(seed, code) for code in codes],
            "phones": [phone if (leg, purpose) == ("DESTINATION", "PICK_UP") else None for leg, purpose in CODES],
        })
    return chunks(found, pick.config["batch"])


def every_shipment(params):
    return [shipment for batch in params for shipment in batch]


def keys(session, params):
    found = every_shipment(params)
    return {
        "order_": [shipment["order"] for shipment in found],
        "shipment_": [shipment["shipment"] for shipment in found],
        "reservation_": [shipment[f"{key}_leg"] for shipment in found for _, key in ROUTE],
        "payment_": [shipment["payment"] for shipment in found],
        "access_code_": [code for shipment in found for code in shipment["code_ids"]],
    }


def missing(shipment):
    return RuntimeError(f"Shipment order {shipment['order']} from locker {shipment['origin']} to "
                        f"{shipment['destination']}: no free {shipment['size']} cell or no tariff")


def ship_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            for shipment in batch:
                rows = conn.execute(SHIP_PG, shipment).fetchall()
                if len(rows) != len(CODES):
                    raise missing(shipment)
                session.driver_counts["access_code_"] += len(rows)


def ship_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            for shipment in batch:
                scalars = {key: value for key, value in shipment.items() if not isinstance(value, list)}
                for _, key in ROUTE:
                    cursor.execute(PICK_MYSQL, scalars | {"locker": shipment[key]})
                    found = cursor.fetchall()
                    if not found:
                        raise missing(shipment)
                    scalars[f"{key}_cell"] = found[0][0]
                cursor.execute(PLACE_MYSQL, scalars)
                if cursor.rowcount != 1:
                    raise missing(shipment)
                cursor.execute(PARCEL_MYSQL, scalars)
                cursor.execute(LEGS_MYSQL, scalars)
                cursor.execute(CHARGE_MYSQL, scalars)
                legs = {leg: shipment[f"{key}_leg"] for leg, key in ROUTE}
                cursor.executemany(CODES_MYSQL, [
                    (code, legs[leg], purpose, checked(hmac), phone, shipment["from"], shipment["to"], shipment["now"])
                    for code, leg, purpose, hmac, phone in zip(shipment["code_ids"], shipment["code_legs"],
                                                               shipment["purposes"], shipment["hmacs"],
                                                               shipment["phones"], strict=True)])
                session.driver_counts["access_code_"] += cursor.rowcount


def candidates(lockers, shipment, key):
    cells = lockers.get(shipment[key], ())
    return [cell["id"] for cell in sorted(cells, key=lambda cell: cell["number"])
            if cell["size"] == shipment["size"] and cell["status"] == "IN_SERVICE"]


def order_document(shipment, tariff, cells):
    legs = []
    for leg, key in ROUTE:
        codes = [{"id": Int64(code), "purpose": purpose, "codeHmac": hmac, "validFrom": shipment["from"],
                  "validTo": shipment["to"], "status": "ACTIVE", "createdAt": shipment["now"]}
                 | ({"sentToPhone": phone} if phone else {})
                 for code, code_leg, purpose, hmac, phone in zip(shipment["code_ids"], shipment["code_legs"],
                                                                 shipment["purposes"], shipment["hmacs"],
                                                                 shipment["phones"], strict=True)
                 if code_leg == leg]
        legs.append({"id": Int64(shipment[f"{key}_leg"]), "size": shipment["size"], "cellId": Int64(cells[key]),
                     "lockermatId": Int64(shipment[key]), "leg": leg, "from": shipment["from"], "to": shipment["to"],
                     "status": "BOOKED", "accessCodes": codes})
    price = Int64(tariff["shipmentPrice"])
    charge = {"id": Int64(shipment["payment"]), "kind": "CHARGE", "amount": price, "status": "COMPLETED",
              "provider": "MOCK", "providerRef": shipment["provider_ref"], "createdAt": shipment["now"],
              "completedAt": shipment["now"]}
    parcel = {"id": Int64(shipment["shipment"]), "recipientName": shipment["recipient_name"],
              "recipientPhone": shipment["recipient_phone"], "declaredValue": Int64(shipment["declared"]),
              "originLockermatId": Int64(shipment["origin"]), "destinationLockermatId": Int64(shipment["destination"])}
    return {"_id": Int64(shipment["order"]), "number": shipment["number"], "customerId": Int64(shipment["customer"]),
            "type": "SHIPMENT", "size": shipment["size"], "tariffId": Int64(tariff["_id"]), "status": "PAID",
            "price": price, "paymentDeadline": shipment["now"] + timedelta(minutes=15), "createdAt": shipment["now"],
            "shipment": parcel, "reservations": legs, "payments": [charge]}


def link_document(shipment):
    return {"_id": Int64(shipment["order"]), "orderId": Int64(shipment["order"]), "from": Int64(shipment["origin"]),
            "to": Int64(shipment["destination"]), "at": shipment["now"]}


def ship_mongo(session, params):
    db = session.handle
    for batch in params:
        with session.transaction() as transaction:
            for shipment in batch:
                tariff = db.tariffs.find_one(tariff_filter(shipment), session=transaction)
                lockers = {locker["_id"]: locker["cells"] for locker in db.lockermats.find(
                    {"_id": {"$in": [shipment[key] for _, key in ROUTE]}, "status": "ACTIVE"}, {"cells": 1},
                    session=transaction)}
                offered = {key: candidates(lockers, shipment, key) for _, key in ROUTE}
                busy = {found["_id"] for found in db.orders.aggregate(
                    busy_pipeline([cell for cells in offered.values() for cell in cells], shipment),
                    session=transaction)}
                free = {key: [cell for cell in offered[key] if cell not in busy] for _, key in ROUTE}
                if not all(free.values()):
                    raise missing(shipment)
                cells = {key: free[key][0] for _, key in ROUTE}
                for _, key in ROUTE:
                    db.lockermats.update_one({"_id": shipment[key], "cells.id": cells[key]},
                                             {"$inc": {"cells.$.guardSeq": 1}}, session=transaction)
                if db.orders.find_one({"reservations": {"$elemMatch": live(list(cells.values()), shipment)}},
                                      {"_id": 1}, session=transaction):
                    raise RuntimeError(f"A cell of shipment order {shipment['order']} is already booked")
                db.orders.insert_one(order_document(shipment, tariff, cells), session=transaction)
                db.shipLinks.insert_one(link_document(shipment), session=transaction)
                session.driver_counts["orders"] += 1


def ship_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            for shipment in batch:
                codes = [{"id": code, "leg": leg, "purpose": purpose, "hmac": hmac.hex(), "phone": phone}
                         for code, leg, purpose, hmac, phone in zip(shipment["code_ids"], shipment["code_legs"],
                                                                    shipment["purposes"], shipment["hmacs"],
                                                                    shipment["phones"], strict=True)]
                found = tx.run(SHIP_CYPHER, shipment | {"codes": codes}).values()
                if not found:
                    raise missing(shipment)
                session.driver_counts["orders"] += len(found)


def orders(params):
    return [Int64(shipment["order"]) for shipment in every_shipment(params)]


def links_mongo(session, params):
    db = session.handle
    found = {"$in": orders(params)}
    by_leg = {}
    shipment = []
    for order in db.orders.find({"_id": found}, {"createdAt": 1, "shipment": 1, "reservations": 1}).sort("_id", 1):
        at = milliseconds(order["createdAt"])
        parcel = order["shipment"]
        shipment.append([order["_id"], parcel["originLockermatId"], parcel["destinationLockermatId"], at])
        lockers = {leg["leg"]: leg["lockermatId"] for leg in order["reservations"]}
        by_leg[order["_id"]] = [order["_id"], lockers["ORIGIN"], lockers["DESTINATION"], at]
    return {
        "shipLinks": [[link["orderId"], link["from"], link["to"], milliseconds(link["at"])]
                      for link in db.shipLinks.find({"_id": found}).sort("_id", 1)],
        "shipment": shipment,
        "reservations": [by_leg[order] for order in sorted(by_leg)],
    }


def links_cypher(session, params):
    return {"SHIPS_TO": [list(row) for row in session.fetch(LINKS_CYPHER, {"orders": orders(params)})]}


SCENARIOS = [Scenario(
    id="C4", op="C", select=shipments, flags=frozenset({"BA", "H1-I"}),
    description="Nadanie przesyłki ×1000: zamówienie, przesyłka, dwie nogi w różnych punktach, cztery kody i opłata "
                "w jednej transakcji, z wyborem taryfy i wolnych skrytek oraz zapisem połączenia między punktami",
    impls={
        "pg": Impl(SHIP_PG, ship_pg, keys=keys),
        "mysql": Impl(SHIP_MYSQL, ship_mysql, keys=keys),
        "mongo": Impl(SHIP_MONGO, ship_mongo, keys=keys, after=links_mongo),
        "neo4j": Impl(SHIP_CYPHER, ship_cypher, keys=keys, after=links_cypher),
    },
)]
