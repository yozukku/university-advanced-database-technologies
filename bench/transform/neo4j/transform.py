import json
import shutil
import struct

import pyarrow as pa
import pyarrow.csv as csv

from bench.check.parquet import connect

BATCH = 100_000
EWKB_POINT = (1, 0x20000001, 4326)
LABELS = {
    "Lockermat": "lockermat_",
    "OpeningHours": "lockermat_opening_hours_",
    "Cell": "lockermat_cell_",
    "Tariff": "tariff_",
    "Customer": "customer_",
    "Order": "order_",
    "Shipment": "shipment_",
    "Reservation": "reservation_",
    "AccessCode": "access_code_",
    "Incident": "incident_",
    "CellOpening": "cell_opening_",
    "Payment": "payment_",
    "AuditEvent": "audit_event_",
}


def instant(column):
    return f"strftime({column}, '%Y-%m-%dT%H:%M:%S.%gZ')"


def clock(column):
    return f"strftime(date '2000-01-01' + {column}, '%H:%M:%S.%f')"


def grosze(column):
    return f"cast({column} * 100 as bigint)"


def edge(table, start, end):
    (start_space, start_column), (end_space, end_column) = start, end
    return f"""
        select {start_column} as ":START_ID({start_space})", {end_column} as ":END_ID({end_space})" from {table}
        where {start_column} is not null and {end_column} is not null
    """


ORDER = f"""
    o.id_ as "id:ID(Order)", o.number_ as number, o.customer_id_ as "customerId:long", o.type_ as type,
    o.size_ as size, o.tariff_id_ as "tariffId:long", o.status_ as status, {grosze("o.price_")} as "price:long",
    {instant("o.payment_deadline_")} as "paymentDeadline:datetime", {instant("o.created_at_")} as "createdAt:datetime",
    {instant("o.closed_at_")} as "closedAt:datetime"
"""
NODES = {
    "Lockermat": f"""
        select id_ as "id:ID(Lockermat)", code_ as code, name_ as name, address_ as address,
               location as "location:point{{crs:WGS-84}}", time_zone_ as timeZone, status_ as status,
               {instant("created_at_")} as "createdAt:datetime"
        from lockermat_ join points using (id_)
    """,
    "OpeningHours": f"""
        select id_ as "id:ID(OpeningHours)", weekday_ as "weekday:int", {clock("opens_at_")} as opensAt,
               {clock("closes_at_")} as closesAt
        from lockermat_opening_hours_
    """,
    "Cell": """
        select id_ as "id:ID(Cell)", number_ as "number:int", size_ as size, status_ as status from lockermat_cell_
    """,
    "Tariff": f"""
        select id_ as "id:ID(Tariff)", size_ as size, {instant("valid_from_")} as "validFrom:datetime",
               {instant("valid_to_")} as "validTo:datetime",
               {grosze("storage_price_per_day_")} as "storagePricePerDay:long",
               {grosze("shipment_price_")} as "shipmentPrice:long",
               {grosze("overstay_price_per_day_")} as "overstayPricePerDay:long"
        from tariff_
    """,
    "Customer": f"""
        select id_ as "id:ID(Customer)", keycloak_id_ as keycloakId, phone_ as phone, company_name_ as companyName,
               tax_id_ as taxId, billing_address_ as billingAddress, terms_version_ as termsVersion,
               {instant("terms_accepted_at_")} as "termsAcceptedAt:datetime",
               {instant("created_at_")} as "createdAt:datetime"
        from customer_
    """,
    "Order": f"""
        select {ORDER} from order_ o anti join shipment_ s on s.order_id_ = o.id_
    """,
    "Order:Shipment": f"""
        select {ORDER}, s.id_ as "shipmentId:long", s.recipient_name_ as recipientName,
               s.recipient_phone_ as recipientPhone, {grosze("s.declared_value_")} as "declaredValue:long",
               s.courier_keycloak_id_ as courierKeycloakId,
               {instant("s.courier_assigned_at_")} as "courierAssignedAt:datetime"
        from order_ o join shipment_ s on s.order_id_ = o.id_
    """,
    "Reservation": f"""
        select id_ as "id:ID(Reservation)", size_ as size, leg_ as leg, {instant("from_")} as "from:datetime",
               {instant("to_")} as "to:datetime", status_ as status,
               {instant("deposited_at_")} as "depositedAt:datetime",
               {instant("collected_at_")} as "collectedAt:datetime"
        from reservation_
    """,
    "AccessCode": f"""
        select id_ as "id:ID(AccessCode)", purpose_ as purpose, lower(hex(code_hmac_)) as codeHmac,
               sent_to_phone_ as sentToPhone, {instant("valid_from_")} as "validFrom:datetime",
               {instant("valid_to_")} as "validTo:datetime", status_ as status,
               {instant("created_at_")} as "createdAt:datetime", {instant("used_at_")} as "usedAt:datetime"
        from access_code_
    """,
    "Incident": f"""
        select id_ as "id:ID(Incident)", cell_id_ as "cellId:long", order_id_ as "orderId:long", source_ as source,
               reported_by_keycloak_id_ as reportedByKeycloakId, type_ as type, description_ as description,
               status_ as status, resolution_ as resolution, resolved_by_keycloak_id_ as resolvedByKeycloakId,
               {instant("created_at_")} as "createdAt:datetime", {instant("resolved_at_")} as "resolvedAt:datetime"
        from incident_
    """,
    "CellOpening": f"""
        select id_ as "id:ID(CellOpening)", incident_id_ as "incidentId:long", channel_ as channel,
               actor_keycloak_id_ as actorKeycloakId, result_ as result,
               {instant("requested_at_")} as "requestedAt:datetime", {instant("closed_at_")} as "closedAt:datetime"
        from cell_opening_
    """,
    "Payment": f"""
        select id_ as "id:ID(Payment)", kind_ as kind, {grosze("amount_")} as "amount:long", status_ as status,
               provider_ as provider, provider_ref_ as providerRef, refund_of_id_ as "refundOfId:long",
               incident_id_ as "incidentId:long", {instant("created_at_")} as "createdAt:datetime",
               {instant("completed_at_")} as "completedAt:datetime"
        from payment_
    """,
    "AuditEvent": f"""
        select id_ as "id:ID(AuditEvent)", {instant("at_")} as "at:datetime", entity_ as entity,
               entity_id_ as "entityId:long", action_ as action, actor_ as actor, changes_ as changes
        from audit_event_
    """,
}
RELATIONSHIPS = {
    kind: edge(table, start, end)
    for kind, table, start, end in (
        ("HAS_HOURS", "lockermat_opening_hours_", ("Lockermat", "lockermat_id_"), ("OpeningHours", "id_")),
        ("HAS_CELL", "lockermat_cell_", ("Lockermat", "lockermat_id_"), ("Cell", "id_")),
        ("PLACED", "order_", ("Customer", "customer_id_"), ("Order", "id_")),
        ("PRICED_BY", "order_", ("Order", "id_"), ("Tariff", "tariff_id_")),
        ("HAS_LEG", "reservation_", ("Order", "order_id_"), ("Reservation", "id_")),
        ("IN_CELL", "reservation_", ("Reservation", "id_"), ("Cell", "cell_id_")),
        ("HAS_CODE", "access_code_", ("Reservation", "reservation_id_"), ("AccessCode", "id_")),
        ("AT_CELL", "incident_", ("Incident", "id_"), ("Cell", "cell_id_")),
        ("ABOUT", "incident_", ("Incident", "id_"), ("Reservation", "reservation_id_")),
        ("OPENED_WITH", "cell_opening_", ("CellOpening", "id_"), ("AccessCode", "access_code_id_")),
        ("OPENED_FOR", "cell_opening_", ("CellOpening", "id_"), ("Incident", "incident_id_")),
        ("HAS_PAYMENT", "payment_", ("Order", "order_id_"), ("Payment", "id_")),
        ("REFUND_OF", "payment_", ("Payment", "id_"), ("Payment", "refund_of_id_")),
        ("COMPENSATES", "payment_", ("Payment", "id_"), ("Incident", "incident_id_")),
    )
}
RELATIONSHIPS["SHIPS_TO"] = f"""
    select oc.lockermat_id_ as ":START_ID(Lockermat)", dc.lockermat_id_ as ":END_ID(Lockermat)",
           s.order_id_ as "orderId:long", {instant("o.created_at_")} as "at:datetime"
    from shipment_ s
    join order_ o on o.id_ = s.order_id_
    join reservation_ ol on ol.order_id_ = s.order_id_ and ol.leg_ = 'ORIGIN'
    join lockermat_cell_ oc on oc.id_ = ol.cell_id_
    join reservation_ dl on dl.order_id_ = s.order_id_ and dl.leg_ = 'DESTINATION'
    join lockermat_cell_ dc on dc.id_ = dl.cell_id_
"""


def points(db):
    ids, locations = [], []
    for id_, location in db.execute("select id_, location_ from lockermat_").fetchall():
        *header, longitude, latitude = struct.unpack("<BIIdd", location)
        if tuple(header) != EWKB_POINT:
            raise ValueError(f"lockermat_ {id_}: location_ is not an EWKB point with SRID 4326")
        ids.append(id_)
        locations.append(f"{{longitude:{longitude!r},latitude:{latitude!r}}}")
    return pa.table({"id_": pa.array(ids, pa.int64()), "location": locations})


def write_csv(db, query, path):
    rows = 0
    reader = db.sql(query).to_arrow_reader(BATCH)
    with csv.CSVWriter(path, reader.schema) as writer:
        for batch in reader:
            writer.write_batch(batch)
            rows += batch.num_rows
    return rows


def write(directory, staging):
    counts = json.loads((directory / "manifest.json").read_text())["counts"]
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    nodes, relationships, expected = [], [], {}
    with connect(directory, counts) as db:
        db.execute("set timezone = 'UTC'")
        db.register("points", points(db))
        for labels, query in NODES.items():
            path = staging / f"{labels.replace(':', '_')}.csv"
            write_csv(db, query, path)
            nodes.append((labels, path))
        for kind, query in RELATIONSHIPS.items():
            path = staging / f"{kind}.csv"
            expected[kind] = write_csv(db, query, path)
            relationships.append((kind, path))
    if expected["SHIPS_TO"] != counts["shipment_"]:
        raise ValueError(f"SHIPS_TO: {expected['SHIPS_TO']} links for {counts['shipment_']} shipments")
    expected.update({label: counts[table] for label, table in LABELS.items()})
    return nodes, relationships, expected
