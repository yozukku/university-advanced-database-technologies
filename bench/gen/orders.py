import heapq
import uuid
from dataclasses import dataclass

import numpy as np
import pyarrow as pa

from .people import company_pool, person_pools
from .slices import unused_lockers
from .static import SIZES, UTC_MS


MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
HISTORY = 730 * DAY
RECENT = 30 * DAY
HORIZON = 30 * DAY
UNPAID = 6 * HOUR
DEADLINE = 15 * MINUTE
OVERDUE = 12 * HOUR
NEW_TERMS = -365 * DAY
FOREVER = 2 ** 62
NULL = np.iinfo(np.int64).min
SIZE_CYCLE = np.array([0, 0, 1, 0, 2, 0, 1, 0, 1, 2], dtype=np.int8)
HEAVY_ORDERS = (60, 80)
PARTNERS = 3
COMPANIES = 512
LEGS = {False: ("STORAGE",), True: ("ORIGIN", "DESTINATION")}
MONEY = pa.decimal128(10, 2)

CUSTOMERS = pa.schema([
    ("id_", pa.int64()), ("keycloak_id_", pa.string()), ("phone_", pa.string()), ("company_name_", pa.string()),
    ("tax_id_", pa.string()), ("billing_address_", pa.string()), ("terms_version_", pa.string()),
    ("terms_accepted_at_", UTC_MS), ("created_at_", UTC_MS),
])
ORDERS = pa.schema([
    ("id_", pa.int64()), ("number_", pa.string()), ("customer_id_", pa.int64()), ("type_", pa.string()),
    ("size_", pa.string()), ("tariff_id_", pa.int64()), ("status_", pa.string()), ("price_", MONEY),
    ("payment_deadline_", UTC_MS), ("created_at_", UTC_MS), ("closed_at_", UTC_MS),
])
RESERVATIONS = pa.schema([
    ("id_", pa.int64()), ("order_id_", pa.int64()), ("order_type_", pa.string()), ("size_", pa.string()), ("cell_id_", pa.int64()),
    ("leg_", pa.string()), ("from_", UTC_MS), ("to_", UTC_MS), ("status_", pa.string()),
    ("deposited_at_", UTC_MS), ("collected_at_", UTC_MS),
])
SHIPMENTS = pa.schema([
    ("id_", pa.int64()), ("order_id_", pa.int64()), ("order_type_", pa.string()), ("recipient_name_", pa.string()),
    ("recipient_phone_", pa.string()), ("declared_value_", MONEY), ("courier_keycloak_id_", pa.string()),
    ("courier_assigned_at_", UTC_MS),
])


@dataclass(frozen=True)
class Orders:
    tables: dict
    paid_at: pa.Array


def order_tables(profile, plan, statics):
    rng = profile.rng(2)
    t0 = int(profile.t0.timestamp())
    parts = [
        (cohort, cohort_orders(rng, cohort, count, count * 3 // 4 if cohort.closed else count // 100, profile.pending_openings))
        for cohort, count in plan.cohorts
    ]

    created = np.concatenate([part["created"] for _, part in parts])
    by_time = np.argsort(created, kind="stable")
    order_id = np.empty(len(created), np.int64)
    order_id[by_time] = np.arange(1, len(created) + 1)
    orders = {
        key: np.concatenate([part[key] for _, part in parts])[by_time]
        for key in ("created", "paid", "closed", "courier")
    }
    orders["status"] = np.concatenate([np.full(len(part["created"]), cohort.status) for cohort, part in parts])[by_time]
    orders["shipment"] = np.concatenate([np.full(len(part["created"]), cohort.shipment) for cohort, part in parts])[by_time]
    sizes = [np.resize(SIZE_CYCLE, len(part["created"])) for _, part in parts]
    orders["size"] = np.concatenate(sizes)[by_time]

    legs = leg_arrays(parts, order_id)
    legs["size"] = orders["size"][legs["order"] - 1]
    legs["cell"] = assign_cells(rng, statics, legs)

    customers = plan.counts["customer_"]
    owner = assign_customers(rng, customers, len(created))
    first = np.full(customers, FOREVER)
    np.minimum.at(first, owner, orders["created"])
    joined = np.where(
        first < FOREVER,
        first - rng.integers(MINUTE, 14 * DAY, customers),
        rng.integers(-HISTORY, -MINUTE, customers),
    )
    by_joined = np.argsort(joined, kind="stable")
    customer_id = np.empty(customers, np.int64)
    customer_id[by_joined] = np.arange(1, customers + 1)
    orders["customer"] = customer_id[owner]

    shipments = int(orders["shipment"].sum())
    customer_pool, recipient_pool = person_pools(profile, customers, max(1, shipments // 4))
    tables = {
        "customer_": customer_table(rng, profile, t0, joined[by_joined], customer_pool),
        "order_": order_table(t0, orders, legs, statics["tariff_"]),
        "reservation_": reservation_table(t0, legs),
        "shipment_": shipment_table(rng, t0, orders, recipient_pool, statics["lockermat_"].num_rows),
    }
    return Orders(tables, stamps(t0, orders["paid"]))


def cohort_orders(rng, cohort, count, old, pending):
    recent = np.arange(count) >= old
    lead = rng.integers(30 * MINUTE, 3 * DAY, count)
    pay = rng.integers(5, DEADLINE - 5, count)
    start = np.zeros(count, np.int64)
    if cohort.shipment:
        origin = window(rng, start, rng.integers(12 * HOUR, 2 * DAY, count))
        windows = [origin, window(rng, origin[1] + 5 * DAY, rng.integers(DAY, 3 * DAY, count))]
    else:
        longest = 8 * HOUR if cohort.legs[0] == "OCCUPIED" else 4 * DAY
        windows = [window(rng, start, rng.integers(2 * HOUR, longest, count))]

    base_created = -lead
    created = base_created.copy()
    earlier = rng.integers(-HISTORY, -RECENT, count)
    closed = np.full(count, NULL)
    if cohort.status == "AWAITING_PAYMENT":
        shift = rng.integers(DAY, HORIZON, count)
        created = np.where(recent, rng.integers(-UNPAID, -DEADLINE, count), earlier) - shift
        fresh = count // 10
        if fresh:
            created[-fresh:] = -5 * MINUTE - shift[-fresh:]
    elif cohort.closed:
        if cohort.status == "COMPLETED":
            closed = windows[-1][3]
        elif cohort.status == "CANCELLED":
            closed = created + pay + rng.integers(1, -(created + pay))
        else:
            closed = created + DEADLINE + rng.integers(0, 2 * MINUTE, count)
        shift = np.where(recent, rng.integers(-RECENT, created - closed), earlier) - created
        closed = shift + closed
    elif set(cohort.legs) == {"BOOKED"}:
        shift = rng.integers(DAY, HORIZON, count)
        created = np.where(recent, rng.integers(-RECENT, -DEADLINE, count), earlier) - shift
        if cohort.name == "storage_booked":
            missed = slice(old, old + count // 4)
            shift[missed] = rng.integers(-15 * DAY, -5 * DAY, count // 4)
            created[missed] = base_created[missed]
            shift[-pending:] = -rng.integers(MINUTE, 2 * MINUTE + 1, pending)
            created[-pending:] = base_created[-pending:]
    else:
        if cohort.legs[-1] == "OCCUPIED":
            deposit, end = windows[-1][2], windows[-1][1]
            shift = -rng.integers(np.maximum(deposit + 1, end - 6 * HOUR), end + 1)
            overdue = count // 2
            shift[:overdue] = -end[:overdue] - rng.integers(1, OVERDUE + 1, overdue)
            shift[:old] = earlier[:old] - created[:old]
        else:
            shift = np.where(recent, -rng.integers(windows[0][3] + DAY, windows[1][0] + 1), earlier - created)

    created = shift + created
    paid = created + pay if cohort.paid else np.full(count, NULL)
    legs = []
    for kind, state, (begin, end, deposit, collect) in zip(LEGS[cohort.shipment], cohort.legs, windows):
        deposit = shift + deposit if state in ("OCCUPIED", "COMPLETED") else np.full(count, NULL)
        collect = shift + collect if state == "COMPLETED" else np.full(count, NULL)
        legs.append((kind, state, shift + begin, shift + end, deposit, collect))
    return {
        "created": created, "paid": paid, "closed": closed,
        "courier": courier_times(rng, cohort, paid, legs), "legs": legs,
    }


def window(rng, start, length):
    deposit = start + rng.integers(0, length // 4)
    remaining = start + length - deposit
    return start, start + length, deposit, deposit + rng.integers(remaining // 5, remaining)


def courier_times(rng, cohort, paid, legs):
    count = len(paid)
    if cohort.shipment and cohort.legs[0] == "COMPLETED":
        return rng.integers(paid + 1, legs[0][5])
    if cohort.shipment and cohort.status == "PAID":
        return np.where(rng.random(count) < 0.5, rng.integers(paid + 1, 0), NULL)
    return np.full(count, NULL)


def leg_arrays(parts, order_id):
    columns = {key: [] for key in ("order", "kind", "status", "from", "to", "deposited", "collected", "until")}
    offset = 0
    for cohort, part in parts:
        count = len(part["created"])
        for kind, state, begin, end, deposit, collect in part["legs"]:
            columns["order"].append(order_id[offset:offset + count])
            columns["kind"].append(np.full(count, kind))
            columns["status"].append(np.full(count, state))
            for key, values in zip(("from", "to", "deposited", "collected"), (begin, end, deposit, collect)):
                columns[key].append(values)
            columns["until"].append(occupied_until(state, end, collect))
        offset += count
    legs = {key: np.concatenate(values) for key, values in columns.items()}
    by_order = np.lexsort((legs["kind"] == "DESTINATION", legs["order"]))
    return {key: values[by_order] for key, values in legs.items()}


def occupied_until(state, end, collect):
    if state == "BOOKED":
        return end
    if state == "OCCUPIED":
        return np.where(end > 0, end, FOREVER)
    if state == "COMPLETED":
        return collect
    return np.full(len(end), NULL)


def assign_cells(rng, statics, legs):
    count_lockers = statics["lockermat_"].num_rows
    lockers = count_lockers - unused_lockers(count_lockers)
    groups = [[[] for _ in SIZES] for _ in range(lockers)]
    cells = statics["lockermat_cell_"]
    for cell, locker, size in zip(*(cells[name].to_pylist() for name in ("id_", "lockermat_id_", "size_"))):
        if locker <= lockers:
            groups[locker - 1][SIZES.index(size)].append(cell)
    heaps = [[[(NULL, cell) for cell in group] for group in locker] for locker in groups]

    count = len(legs["order"])
    weights = rng.lognormal(0.0, 0.6, lockers)
    preferred = rng.choice(lockers, count, p=weights / weights.sum()).tolist()
    partners = partner_lockers(rng, lockers)
    slot = rng.integers(0, len(partners[0]), count).tolist()
    pick = rng.integers(0, 1 << 30, count).tolist()
    destination = (legs["kind"] == "DESTINATION").tolist()
    size = legs["size"].tolist()
    begin = legs["from"].tolist()
    until = legs["until"].tolist()
    locker_of = [0] * count
    cell_of = [0] * count

    def choice(index):
        if destination[index]:
            origin = locker_of[index - 1]
            return partners[origin][slot[index]], origin
        return preferred[index], -1

    packed = np.flatnonzero(legs["until"] != NULL)
    for index in packed[np.lexsort((packed, legs["from"][packed]))].tolist():
        first, avoid = choice(index)
        for step in range(lockers):
            locker = (first + step) % lockers
            heap = heaps[locker][size[index]]
            if locker != avoid and heap[0][0] <= begin[index]:
                cell_of[index] = heapq.heapreplace(heap, (until[index], heap[0][1]))[1]
                locker_of[index] = locker
                break
        else:
            raise RuntimeError(f"No free {SIZES[size[index]]} cell for reservation {index + 1}")

    for index in np.flatnonzero(legs["until"] == NULL).tolist():
        locker, _ = choice(index)
        group = groups[locker][size[index]]
        cell_of[index] = group[pick[index] % len(group)]
        locker_of[index] = locker
    return np.array(cell_of, np.int64)


def partner_lockers(rng, lockers):
    count = min(PARTNERS, lockers - 1)
    result = []
    for locker in range(lockers):
        others = rng.choice(lockers - 1, count, replace=False)
        result.append([int(other + (other >= locker)) for other in others])
    return result


def assign_customers(rng, customers, orders):
    slots = rng.permutation(customers)
    heavy = slots[:customers // 100]
    regular = slots[customers // 100 + customers // 20:]
    counts = rng.integers(HEAVY_ORDERS[0], HEAVY_ORDERS[1] + 1, len(heavy))
    rest = orders - counts.sum() - len(regular)
    owners = np.concatenate([np.repeat(heavy, counts), regular, regular[rng.integers(0, len(regular), rest)]])
    result = np.empty(orders, np.int64)
    result[rng.permutation(orders)] = owners
    return result


def customer_table(rng, profile, t0, joined, pool):
    count = len(joined)
    keycloak = [str(uuid.UUID(bytes=rng.bytes(16), version=4)) for _ in range(count)]
    has_phone = rng.random(count) >= 0.1
    business = (rng.random(count) < 0.05).tolist()
    companies = company_pool(profile, COMPANIES)
    company = [companies[index] for index in rng.integers(0, COMPANIES, count)]
    tax = rng.integers(10 ** 9, 10 ** 10, count).tolist()
    terms = np.where(joined < NEW_TERMS, "2024-11", "2025-11")
    return pa.Table.from_arrays([
        pa.array(np.arange(1, count + 1), pa.int64()),
        pa.array(keycloak, pa.string()),
        pa.array([person.phone if flag else None for person, flag in zip(pool, has_phone)], pa.string()),
        pa.array([entry.name if flag else None for entry, flag in zip(company, business)], pa.string()),
        pa.array([str(value) if flag else None for value, flag in zip(tax, business)], pa.string()),
        pa.array([entry.address if flag else None for entry, flag in zip(company, business)], pa.string()),
        pa.array(terms, pa.string()),
        stamps(t0, joined),
        stamps(t0, joined),
    ], schema=CUSTOMERS)


def order_table(t0, orders, legs, tariffs):
    count = len(orders["created"])
    tariff = tariff_ids(t0, tariffs, orders["size"], orders["created"])
    rows = {row["id_"]: row for row in tariffs.to_pylist()}
    per_day = np.array([0] + [grosze(rows[key]["storage_price_per_day_"]) for key in sorted(rows)])
    shipment_price = np.array([0] + [grosze(rows[key]["shipment_price_"]) for key in sorted(rows)])
    days = np.ones(count, np.int64)
    storage = legs["kind"] == "STORAGE"
    days[legs["order"][storage] - 1] = -(-(legs["to"][storage] - legs["from"][storage]) // DAY)
    price = np.where(orders["shipment"], shipment_price[tariff], per_day[tariff] * days)
    return pa.Table.from_arrays([
        pa.array(np.arange(1, count + 1), pa.int64()),
        pa.array([f"BAG-{index:010d}" for index in range(1, count + 1)], pa.string()),
        pa.array(orders["customer"], pa.int64()),
        pa.array(np.where(orders["shipment"], "SHIPMENT", "STORAGE"), pa.string()),
        pa.array(np.array(SIZES)[orders["size"]], pa.string()),
        pa.array(tariff, pa.int64()),
        pa.array(orders["status"], pa.string()),
        money(price),
        stamps(t0, orders["created"] + DEADLINE),
        stamps(t0, orders["created"]),
        stamps(t0, orders["closed"]),
    ], schema=ORDERS)


def tariff_ids(t0, tariffs, size, created):
    result = np.zeros(len(size), np.int64)
    rows = tariffs.to_pylist()
    for group, name in enumerate(SIZES):
        options = sorted((int(row["valid_from_"].timestamp()) - t0, row["id_"]) for row in rows if row["size_"] == name)
        mask = size == group
        position = np.searchsorted([start for start, _ in options], created[mask], side="right") - 1
        result[mask] = np.array([identifier for _, identifier in options])[position]
    return result


def reservation_table(t0, legs):
    count = len(legs["order"])
    return pa.Table.from_arrays([
        pa.array(np.arange(1, count + 1), pa.int64()),
        pa.array(legs["order"], pa.int64()),
        pa.array(np.where(legs["kind"] == "STORAGE", "STORAGE", "SHIPMENT"), pa.string()),
        pa.array(np.array(SIZES)[legs["size"]], pa.string()),
        pa.array(legs["cell"], pa.int64()),
        pa.array(legs["kind"], pa.string()),
        stamps(t0, legs["from"]),
        stamps(t0, legs["to"]),
        pa.array(legs["status"], pa.string()),
        stamps(t0, legs["deposited"]),
        stamps(t0, legs["collected"]),
    ], schema=RESERVATIONS)


def shipment_table(rng, t0, orders, pool, lockers):
    order_ids = np.flatnonzero(orders["shipment"]) + 1
    count = len(order_ids)
    recipients = [pool[index] for index in rng.integers(0, len(pool), count)]
    couriers = [str(uuid.UUID(bytes=rng.bytes(16), version=4)) for _ in range(max(2, lockers // 10))]
    assigned = orders["courier"][order_ids - 1]
    courier = [couriers[index] for index in rng.integers(0, len(couriers), count)]
    return pa.Table.from_arrays([
        pa.array(np.arange(1, count + 1), pa.int64()),
        pa.array(order_ids, pa.int64()),
        pa.array(np.repeat("SHIPMENT", count), pa.string()),
        pa.array([person.name for person in recipients], pa.string()),
        pa.array([person.phone for person in recipients], pa.string()),
        money(rng.integers(5, 201, count) * 1000),
        pa.array([value if at != NULL else None for value, at in zip(courier, assigned)], pa.string()),
        stamps(t0, assigned),
    ], schema=SHIPMENTS)


def grosze(value):
    return int(value * 100)


def money(values):
    values = np.asarray(values, dtype=np.int64)
    limbs = np.empty((len(values), 2), dtype="<i8")
    limbs[:, 0] = values
    limbs[:, 1] = np.where(values < 0, -1, 0)
    return pa.Array.from_buffers(MONEY, len(values), [None, pa.py_buffer(limbs)])


def stamps(t0, seconds):
    missing = seconds == NULL
    return pa.array((t0 + np.where(missing, 0, seconds)) * 1000, UTC_MS, mask=missing)
