import json
import struct
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256

import pyarrow as pa
import pyarrow.parquet as pq

from bench.check.parquet import connect

TABLES = (
    "lockermat_", "lockermat_opening_hours_", "lockermat_cell_", "tariff_", "customer_", "order_", "reservation_",
    "shipment_", "access_code_", "incident_", "cell_opening_", "payment_", "audit_event_",
)
DERIVED = {
    "reservations.lockermatId": ("int", "int"),
    "shipment.lockermatIds": ("int", "int", "int"),
    "shipLinks": ("int", "int", "int", "int", "ms"),
    "SHIPS_TO": ("int", "int", "int", "ms"),
    "changes_new_": ("int", "json"),
}
TYPES = (
    (pa.types.is_timestamp, "ms"), (pa.types.is_time, "clock"), (pa.types.is_decimal, "grosze"),
    (pa.types.is_fixed_size_binary, "hex"), (pa.types.is_integer, "int"),
)
BATCH = 10_000
MODULUS = 2 ** 256
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MILLISECOND = timedelta(milliseconds=1)
SHIPMENT_LOCKERS = """
    select s.order_id_, o.created_at_, oc.lockermat_id_ as origin_, dc.lockermat_id_ as destination_
    from shipment_ s
    join order_ o on o.id_ = s.order_id_
    join reservation_ ol on ol.order_id_ = s.order_id_ and ol.leg_ = 'ORIGIN'
    join lockermat_cell_ oc on oc.id_ = ol.cell_id_
    join reservation_ dl on dl.order_id_ = s.order_id_ and dl.leg_ = 'DESTINATION'
    join lockermat_cell_ dc on dc.id_ = dl.cell_id_
"""
CANONICAL_DERIVED = {
    "reservations.lockermatId": """
        select r.id_, c.lockermat_id_ from reservation_ r join lockermat_cell_ c on c.id_ = r.cell_id_
    """,
    "shipment.lockermatIds": f"select order_id_, origin_, destination_ from ({SHIPMENT_LOCKERS})",
    "shipLinks": f"select order_id_, order_id_, origin_, destination_, epoch_ms(created_at_) from ({SHIPMENT_LOCKERS})",
    "SHIPS_TO": f"select order_id_, origin_, destination_, epoch_ms(created_at_) from ({SHIPMENT_LOCKERS})",
}


def kind(field):
    if field.name == "location_":
        return "point"
    if field.name in ("actor_", "changes_"):
        return "json"
    return next((name for test, name in TYPES if test(field.type)), "text")


def read_schema(directory):
    return {table: [(field.name, kind(field)) for field in pq.read_schema(directory / f"{table}.parquet")]
            for table in TABLES}


def kinds(schema):
    return {table: [kind for _, kind in columns] for table, columns in schema.items()} | DERIVED


def text(value):
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def milliseconds(value):
    if isinstance(value, int):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (value - EPOCH) // MILLISECOND


def clock(value):
    if isinstance(value, timedelta):
        value = (datetime.min + value).time()
    return value if isinstance(value, str) else value.strftime("%H:%M:%S.%f")


def grosze(value):
    return int(value * 100) if isinstance(value, Decimal) else int(value)


def hexadecimal(value):
    return value if isinstance(value, str) else bytes(value).hex()


def point(value):
    if isinstance(value, (bytes, bytearray)):
        if value[0] != 1:
            raise ValueError("location is not little-endian WKB")
        return list(struct.unpack("<dd", bytes(value[-16:])))
    if isinstance(value, dict):
        return list(value["coordinates"])
    return [value.longitude, value.latitude]


def parsed(value):
    return json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value


NORMALISE = {
    "int": int, "text": text, "ms": milliseconds, "clock": clock, "grosze": grosze, "hex": hexadecimal,
    "point": point, "json": parsed,
}


def row_hash(row):
    encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return int.from_bytes(sha256(encoded).digest())


def digest(rows, kinds):
    totals = {}
    for name, values in rows:
        pairs = zip(kinds[name], values, strict=True)
        row = [None if value is None else NORMALISE[kind](value) for kind, value in pairs]
        count, total = totals.get(name, (0, 0))
        totals[name] = (count + 1, (total + row_hash(row)) % MODULUS)
    return {name: {"rows": count, "hash": f"{total:064x}"} for name, (count, total) in totals.items()}


def batches(cursor, name):
    while batch := cursor.fetchmany(BATCH):
        for values in batch:
            yield name, values


def string_values(changes):
    if changes is None:
        return None
    return [change["new"] for change in json.loads(changes) if isinstance(change.get("new"), str)]


def canonical_rows(directory, schema):
    with connect(directory, TABLES) as db:
        db.execute("set timezone = 'UTC'")
        for table in TABLES:
            select = ", ".join(f"epoch_ms({name})" if kind == "ms" else name for name, kind in schema[table])
            yield from batches(db.execute(f"select {select} from {table}"), table)
        for name, query in CANONICAL_DERIVED.items():
            yield from batches(db.execute(query), name)
        for _, (id_, changes) in batches(db.execute("select id_, changes_ from audit_event_"), None):
            yield "changes_new_", (id_, string_values(changes))
