from hashlib import sha256

import numpy as np
import pyarrow as pa

from .orders import DAY, MINUTE, NULL, money
from .static import UTC_MS


STAFF = "9b8afa41-c8c1-43ad-99e4-624367d0ae1d"
CODE_SCHEMA = pa.schema([
    ("id_", pa.int64()), ("reservation_id_", pa.int64()), ("purpose_", pa.string()),
    ("code_hmac_", pa.binary(32)), ("sent_to_phone_", pa.string()), ("valid_from_", UTC_MS),
    ("valid_to_", UTC_MS), ("status_", pa.string()), ("created_at_", UTC_MS), ("used_at_", UTC_MS),
])
OPENING_SCHEMA = pa.schema([
    ("id_", pa.int64()), ("access_code_id_", pa.int64()), ("incident_id_", pa.int64()),
    ("channel_", pa.string()), ("actor_keycloak_id_", pa.string()), ("result_", pa.string()),
    ("requested_at_", UTC_MS), ("closed_at_", UTC_MS),
])
PAYMENT_SCHEMA = pa.schema([
    ("id_", pa.int64()), ("order_id_", pa.int64()), ("kind_", pa.string()),
    ("amount_", pa.decimal128(10, 2)), ("status_", pa.string()), ("provider_", pa.string()),
    ("provider_ref_", pa.string()), ("refund_of_id_", pa.int64()), ("incident_id_", pa.int64()),
    ("refundable_id_", pa.int64()), ("created_at_", UTC_MS), ("completed_at_", UTC_MS),
])
INCIDENT_SCHEMA = pa.schema([
    ("id_", pa.int64()), ("cell_id_", pa.int64()), ("reservation_id_", pa.int64()),
    ("order_id_", pa.int64()), ("source_", pa.string()), ("reported_by_keycloak_id_", pa.string()),
    ("type_", pa.string()), ("description_", pa.string()), ("status_", pa.string()),
    ("resolution_", pa.string()), ("resolved_by_keycloak_id_", pa.string()),
    ("created_at_", UTC_MS), ("resolved_at_", UTC_MS),
])


def ledger_tables(profile, plan, orders):
    t0 = int(profile.t0.timestamp()) * 1000
    rng = profile.rng(3)
    order = orders.tables["order_"]
    reservation = orders.tables["reservation_"]
    shipment = orders.tables["shipment_"]
    paid = millis(orders.paid_at)
    codes = access_codes(profile.seed, t0, paid, reservation, shipment, rng)

    incidents = make_incidents(plan.counts["incident_"], t0, order, reservation, rng)
    yield "access_code_", codes
    yield "payment_", make_payments(order, paid)
    yield "incident_", incidents
    yield "cell_opening_", make_openings(profile, plan, t0, codes, incidents, reservation, rng)


def col(table, name):
    return table[name].combine_chunks().to_numpy(zero_copy_only=False)


def millis(column):
    return column.cast(pa.int64()).fill_null(NULL).to_numpy(zero_copy_only=False)


def timestamps(values):
    return pa.array(values, UTC_MS, mask=values == NULL)


def optional_ids(values):
    return pa.array(values, pa.int64(), mask=values == 0)


def access_codes(seed, t0, paid, reservation, shipment, rng):
    order_index = col(reservation, "order_id_") - 1
    paid_rows = np.flatnonzero(paid[order_index] != NULL)
    rows = np.repeat(paid_rows, 2)
    count = len(rows)
    ids = np.arange(1, count + 1)
    pickup = np.arange(count) % 2 == 1
    kind = col(reservation, "leg_")[rows]
    status = col(reservation, "status_")[rows]
    starts = millis(reservation["from_"])[rows]
    ends = millis(reservation["to_"])[rows]
    used = np.where(pickup, millis(reservation["collected_at_"])[rows], millis(reservation["deposited_at_"])[rows])
    code_status = np.where(used != NULL, "USED", np.where(status == "CANCELLED", "REVOKED", "ACTIVE"))
    expired = np.flatnonzero((code_status == "ACTIVE") & (ends < t0))
    target = count // 20
    if len(expired) < target:
        raise ValueError(f"Only {len(expired)} expired active code candidates for {target} rows")
    rng.shuffle(expired)
    code_status[expired[target:]] = "REVOKED"
    recipient = dict(zip(col(shipment, "order_id_"), col(shipment, "recipient_phone_")))
    sent = np.full(count, None, dtype=object)
    destination_pickup = np.flatnonzero(pickup & (kind == "DESTINATION"))
    sent[destination_pickup] = [recipient[key] for key in col(reservation, "order_id_")[rows[destination_pickup]]]
    hash_prefix = seed.to_bytes(8, "big")
    return pa.Table.from_arrays([
        pa.array(ids), pa.array(col(reservation, "id_")[rows]), pa.array(np.where(pickup, "PICK_UP", "DROP_OFF")),
        pa.array([sha256(hash_prefix + int(identifier).to_bytes(8, "big")).digest() for identifier in ids], pa.binary(32)),
        pa.array(sent, pa.string()), timestamps(starts), timestamps(ends), pa.array(code_status),
        timestamps(paid[order_index[rows]]), timestamps(used),
    ], schema=CODE_SCHEMA)


def make_payments(order, paid):
    count = order.num_rows
    ids = np.arange(1, count + 1)
    cancelled = col(order, "status_") == "CANCELLED"
    captured = paid != NULL
    matching = ids[cancelled]
    refund_ids = np.arange(count + 1, count + 1 + len(matching))
    owns = np.concatenate((ids, matching))
    completed = np.concatenate((paid, millis(order["closed_at_"])[cancelled]))
    amounts = col(order, "price_")
    charge_status = np.where(captured, "COMPLETED", np.where(col(order, "status_") == "EXPIRED", "CANCELLED", "PENDING"))
    total = len(owns)
    identifiers = np.concatenate((ids, refund_ids))
    return pa.Table.from_arrays([
        pa.array(identifiers), pa.array(owns), pa.array(np.where(identifiers <= count, "CHARGE", "REFUND")),
        money(np.fromiter((int(amounts[index - 1] * 100) for index in owns), dtype=np.int64, count=total)),
        pa.array(np.concatenate((charge_status, np.repeat("COMPLETED", len(matching))))),
        pa.array(np.repeat("MOCK", total)),
        pa.array([f"MOCK-{value:010d}" if time != NULL else None for value, time in zip(identifiers, completed)], pa.string()),
        optional_ids(np.concatenate((np.zeros(count, dtype=np.int64), matching))),
        pa.nulls(total, pa.int64()),
        optional_ids(np.concatenate((np.where(captured, ids, 0), np.zeros(len(matching), dtype=np.int64)))),
        timestamps(np.concatenate((millis(order["created_at_"]) + 1, millis(order["closed_at_"])[cancelled]))),
        timestamps(completed),
    ], schema=PAYMENT_SCHEMA)


def make_incidents(count, t0, order, reservation, rng):
    rows = rng.choice(reservation.num_rows, count, replace=False)
    order_ids = col(reservation, "order_id_")[rows]
    created = millis(order["created_at_"])[order_ids - 1]
    requested = created + rng.integers(1000, np.minimum(t0 - created - 1000, 6 * DAY * 1000), count)
    resolved = (requested < t0 - 2 * DAY * 1000) & (rng.random(count) < 0.65)
    return pa.Table.from_arrays([
        pa.array(np.arange(1, count + 1)), pa.array(col(reservation, "cell_id_")[rows]),
        pa.array(col(reservation, "id_")[rows]), pa.array(order_ids),
        pa.array(np.where(rng.random(count) < 0.3, "CUSTOMER", "TERMINAL")), pa.nulls(count, pa.string()),
        pa.array(rng.choice(["DOOR_WONT_OPEN", "CELL_NOT_EMPTY", "DOOR_LEFT_OPEN"], count)),
        pa.array(np.repeat("Zgłoszenie dotyczące skrytki", count)),
        pa.array(np.where(resolved, "RESOLVED", "OPEN")),
        pa.array(np.repeat("Sprawdzono skrytkę", count), pa.string(), mask=~resolved),
        pa.array(np.repeat(STAFF, count), pa.string(), mask=~resolved),
        timestamps(requested), timestamps(np.where(resolved, requested + DAY * 1000, NULL)),
    ], schema=INCIDENT_SCHEMA)


def make_openings(profile, plan, t0, codes, incidents, reservation, rng):
    used_at = millis(codes["used_at_"])
    starts = millis(codes["valid_from_"])
    ends = millis(codes["valid_to_"])
    issued = millis(codes["created_at_"])
    codes_by_leg = col(codes, "reservation_id_") - 1
    used = np.flatnonzero(used_at != NULL)
    failed_candidates = used[(used_at[used] - np.maximum(starts[used], issued[used])) > 1]
    failed = rng.choice(failed_candidates, plan.failed_openings, replace=False)
    states = col(reservation, "status_")[codes_by_leg]
    pending = np.flatnonzero(
        (col(codes, "purpose_") == "DROP_OFF") & (states == "BOOKED")
        & (col(reservation, "leg_")[codes_by_leg] == "STORAGE")
        & (starts >= t0 - 2 * MINUTE * 1000) & (starts < t0) & (ends > t0)
    )
    if len(pending) != profile.pending_openings:
        raise ValueError(f"Expected {profile.pending_openings} pending codes, found {len(pending)}")

    service_count = plan.counts["cell_opening_"] - len(used) - len(failed) - len(pending)
    incident_rows = rng.integers(0, incidents.num_rows, service_count)
    incident_time = millis(incidents["created_at_"])[incident_rows]
    floor = np.maximum(incident_time, t0 - 180 * DAY * 1000)
    service_at = floor + rng.integers(1, t0 - floor, service_count)
    code_count = len(used) + len(failed) + len(pending)
    total = code_count + service_count
    requested = np.concatenate((used_at[used], used_at[failed] - 1, np.full(len(pending), t0 - 1), service_at))
    result = np.concatenate((
        np.repeat("OPENED", len(used)),
        np.repeat("DOOR_FAILED", len(failed)),
        np.repeat("PENDING", len(pending)),
        np.repeat("OPENED", service_count),
    ))
    service = np.arange(total) >= code_count
    closed = np.where(result == "OPENED", np.minimum(requested + 1000, t0 - 1), NULL)
    return pa.Table.from_arrays([
        pa.array(np.arange(1, total + 1)),
        optional_ids(np.concatenate((used + 1, failed + 1, pending + 1, np.zeros(service_count, dtype=np.int64)))),
        optional_ids(np.concatenate((np.zeros(code_count, dtype=np.int64), incident_rows + 1))),
        pa.array(np.where(service, "SERVICE", "KEYPAD")),
        pa.array(np.repeat(STAFF, total), pa.string(), mask=~service),
        pa.array(result), timestamps(requested), timestamps(closed),
    ], schema=OPENING_SCHEMA)
