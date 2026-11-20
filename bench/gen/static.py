import struct
from datetime import time, timedelta
from decimal import Decimal

import numpy as np
import pyarrow as pa

from .cities import ANCHORS, CITIES


UTC_MS = pa.timestamp("ms", tz="UTC")
WKB_POINT = struct.Struct("<BIIdd")
SIZES = ("S", "M", "L")

LOCKERS = pa.schema([
    ("id_", pa.int64()), ("code_", pa.string()), ("name_", pa.string()), ("address_", pa.string()),
    ("location_", pa.binary(25)), ("time_zone_", pa.string()), ("status_", pa.string()),
    ("created_at_", UTC_MS),
])
CELLS = pa.schema([
    ("id_", pa.int64()), ("lockermat_id_", pa.int64()), ("number_", pa.int16()),
    ("size_", pa.string()), ("status_", pa.string()),
])
HOURS = pa.schema([
    ("id_", pa.int64()), ("lockermat_id_", pa.int64()), ("weekday_", pa.int16()),
    ("opens_at_", pa.time64("us")), ("closes_at_", pa.time64("us")),
])
TARIFFS = pa.schema([
    ("id_", pa.int64()), ("size_", pa.string()), ("valid_from_", UTC_MS), ("valid_to_", UTC_MS),
    ("storage_price_per_day_", pa.decimal128(8, 2)), ("shipment_price_", pa.decimal128(8, 2)),
    ("overstay_price_per_day_", pa.decimal128(8, 2)),
])


def static_tables(profile, plan):
    lockers = plan.counts["lockermat_"]
    yield "lockermat_", lockermats(profile, lockers)
    yield "lockermat_cell_", cells(lockers)
    yield "lockermat_opening_hours_", hours(lockers, plan.counts["lockermat_opening_hours_"])
    yield "tariff_", tariffs(profile)


def lockermats(profile, count):
    rng = profile.rng(1)
    weights = np.array([city[3] for city in CITIES], dtype=np.float64)
    initial = min(count, len(CITIES))
    city_ids = np.concatenate((np.arange(initial), rng.choice(len(CITIES), count - initial, p=weights / weights.sum())))
    jitter = rng.uniform(-0.014, 0.014, (count, 2))
    rows = []
    for index, city_id in enumerate(city_ids):
        city, longitude, latitude, _ = CITIES[city_id]
        if index < len(ANCHORS):
            name, longitude, latitude = ANCHORS[index]
        else:
            name = f"{city} · Punkt {index + 1}"
            longitude += jitter[index, 0]
            latitude += jitter[index, 1]
        rows.append({
            "id_": index + 1, "code_": f"LM-{index + 1:06}", "name_": name, "address_": f"{city}, punkt {index + 1}",
            "location_": WKB_POINT.pack(1, 0x20000001, 4326, longitude, latitude),
            "time_zone_": "Europe/Warsaw", "status_": "ACTIVE",
            "created_at_": profile.t0 - timedelta(days=1200),
        })
    return pa.Table.from_pylist(rows, schema=LOCKERS)


def cells(lockers):
    return pa.Table.from_arrays([
        pa.array(np.arange(1, lockers * 40 + 1), type=pa.int64()),
        pa.array(np.repeat(np.arange(1, lockers + 1), 40), type=pa.int64()),
        pa.array(np.tile(np.arange(1, 41, dtype=np.int16), lockers)),
        pa.array(np.tile(np.repeat(SIZES, [20, 12, 8]), lockers)),
        pa.array(np.repeat("IN_SERVICE", lockers * 40)),
    ], schema=CELLS)


def hours(lockers, total):
    base, remainder = divmod(total, lockers)
    rows = [
        (locker, weekday, time(6), time(23))
        for locker in range(1, lockers + 1)
        for weekday in range(1, base + (locker <= remainder) + 1)
    ]
    return pa.Table.from_pylist([
        dict(zip(HOURS.names, (index, *row))) for index, row in enumerate(rows, start=1)
    ], schema=HOURS)


def tariffs(profile):
    rows = []
    prices = ((15, 39, 20), (20, 49, 25), (30, 59, 35))
    boundaries = [profile.t0 - timedelta(days=days) for days in (1500, 750, 365)] + [None]
    for size, price in zip(SIZES, prices):
        for period, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            values = tuple(Decimal(value - (2 - period)) for value in price)
            rows.append(dict(zip(TARIFFS.names, (len(rows) + 1, size, start, end, *values))))
    return pa.Table.from_pylist(rows, schema=TARIFFS)
