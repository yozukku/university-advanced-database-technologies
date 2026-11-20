import json

import numpy as np
import pyarrow as pa

from .ledger import STAFF, col, millis, timestamps
from .orders import NULL
from .static import UTC_MS


AUDIT_SCHEMA = pa.schema([
    ("id_", pa.int64()), ("at_", UTC_MS), ("entity_", pa.string()), ("entity_id_", pa.int64()),
    ("action_", pa.string()), ("actor_", pa.string()), ("changes_", pa.string()),
])


class AuditEvents:
    def __init__(self):
        self.next_id = 1
        self.batches = []

    def add(self, at, entity, ids, action, actor, old, new):
        count = len(ids)
        if not count:
            return
        values = pa.array(actor if not isinstance(actor, str) else [actor] * count, pa.string())
        change = encode([{"f": "status_", "old": old, "new": new}])
        self.batches.append(pa.record_batch([
            pa.array(np.arange(self.next_id, self.next_id + count)),
            timestamps(at), pa.array([entity] * count), pa.array(ids), pa.array([action] * count),
            values, pa.array([change] * count),
        ], schema=AUDIT_SCHEMA))
        self.next_id += count

    def table(self):
        return pa.Table.from_batches(self.batches, schema=AUDIT_SCHEMA)


def audit_events(orders, payments, cells):
    order = orders.tables["order_"]
    reservation = orders.tables["reservation_"]
    shipment = orders.tables["shipment_"]
    actors = customer_actors(orders)
    owned = actors[col(order, "customer_id_") - 1]
    events = AuditEvents()

    add_order_events(events, order, millis(orders.paid_at), owned, payments)
    add_reservation_events(events, reservation, shipment, cells, owned)
    add_refunds(events, payments)
    return events.table()


def customer_actors(orders):
    keycloak = col(orders.tables["customer_"], "keycloak_id_")
    return np.asarray([
        encode({"kind": "CUSTOMER", "keycloak_id": identifier, "email": person.email})
        for identifier, person in zip(keycloak, orders.customer_pool)
    ], dtype=object)


def provider_actors(provider, references):
    return [encode({"kind": "PROVIDER", "provider": label, "provider_ref": reference})
            for label, reference in zip(provider, references)]


def add_order_events(events, order, paid_at, actors, payments):
    identifiers = col(order, "id_")
    created = millis(order["created_at_"])
    closed = millis(order["closed_at_"])
    status = col(order, "status_")
    events.add(created, "ORDER", identifiers, "CREATED", actors, None, "AWAITING_PAYMENT")

    paid = paid_at != NULL
    payments_for_order = payments.slice(0, order.num_rows)
    captured = provider_actors(col(payments_for_order, "provider_")[paid], col(payments_for_order, "provider_ref_")[paid])
    events.add(paid_at[paid], "ORDER", identifiers[paid], "PAID", captured, "AWAITING_PAYMENT", "PAID")

    cancelled = status == "CANCELLED"
    cancellation_actors = actors[cancelled].copy()
    cancellation_actors[identifiers[cancelled] % 11 == 0] = encode({"kind": "SUPPORT", "keycloak_id": STAFF})
    events.add(closed[cancelled], "ORDER", identifiers[cancelled], "CANCELLED", cancellation_actors, "PAID", "CANCELLED")

    expired = status == "EXPIRED"
    system = encode({"kind": "SYSTEM", "job": "expire-orders"})
    events.add(closed[expired], "ORDER", identifiers[expired], "EXPIRED", system, "AWAITING_PAYMENT", "EXPIRED")


def add_reservation_events(events, reservations, shipments, cells, owners):
    ids = col(reservations, "id_")
    order = col(reservations, "order_id_") - 1
    legs = col(reservations, "leg_")
    deposits = millis(reservations["deposited_at_"])
    collections = millis(reservations["collected_at_"])
    courier, recipient = shipment_actors(shipments, len(owners))
    lockers = col(cells, "lockermat_id_")[col(reservations, "cell_id_") - 1]
    terminals = np.asarray([encode({"kind": "TERMINAL", "lockermat_id": i})
                            for i in range(1, int(lockers.max()) + 1)], dtype=object)

    deposited = deposits != NULL
    dep_actors = np.where(legs[deposited] == "DESTINATION", courier[order[deposited]], owners[order[deposited]])
    local = (legs[deposited] != "DESTINATION") & (ids[deposited] % 7 == 0)
    dep_actors[local] = terminals[lockers[deposited][local] - 1]
    events.add(deposits[deposited], "RESERVATION", ids[deposited], "DEPOSITED", dep_actors, "BOOKED", "OCCUPIED")

    collected = collections != NULL
    col_actors = owners[order[collected]].copy()
    recipients = legs[collected] == "DESTINATION"
    couriers = legs[collected] == "ORIGIN"
    col_actors[recipients] = recipient[order[collected][recipients]]
    col_actors[couriers] = courier[order[collected][couriers]]
    events.add(collections[collected], "RESERVATION", ids[collected], "COLLECTED", col_actors, "OCCUPIED", "COMPLETED")


def shipment_actors(shipments, order_count):
    rows = col(shipments, "order_id_") - 1
    couriers = np.full(order_count, None, dtype=object)
    recipients = np.full(order_count, None, dtype=object)
    couriers[rows] = [encode({"kind": "COURIER", "keycloak_id": value}) if value is not None else None
                      for value in col(shipments, "courier_keycloak_id_")]
    recipients[rows] = [encode({"kind": "RECIPIENT", "name": name, "phone": phone})
                        for name, phone in zip(col(shipments, "recipient_name_"), col(shipments, "recipient_phone_"))]
    return couriers, recipients


def add_refunds(events, payments):
    refund = col(payments, "kind_") == "REFUND"
    actors = provider_actors(col(payments, "provider_")[refund], col(payments, "provider_ref_")[refund])
    events.add(
        millis(payments["completed_at_"])[refund],
        "PAYMENT", col(payments, "id_")[refund], "REFUNDED", actors, None, "COMPLETED",
    )


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
