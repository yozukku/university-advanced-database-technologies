from pathlib import Path

import numpy as np
import yaml

from bench.gen.static import WKB_POINT

from .ledger import SLICE_QUERIES


T0 = "getvariable('benchmark_t0')"
SCENARIOS = {f"{op}{number}" for op, count in (("C", 6), ("R", 8), ("U", 6), ("D", 6), ("J", 6))
             for number in range(1, count + 1)}
COUNTS = {
    "R1": """select count(*) from order_ o where exists (select 1 from reservation_ r where r.order_id_ = o.id_)
              and exists (select 1 from payment_ p where p.order_id_ = o.id_)""",
    "R4": """select count(distinct s.recipient_phone_) from shipment_ s join reservation_ r
                 on r.order_id_ = s.order_id_ and r.leg_ = 'DESTINATION' and r.status_ = 'OCCUPIED'
              where s.recipient_phone_ in (select recipient_phone_ from shipment_ group by 1 having count(*) > 1)""",
    "U1": "select count(*) from order_ where status_ = 'PAID'",
    "U2": SLICE_QUERIES["pending openings"],
    "U3": SLICE_QUERIES["unpaid orders past deadline"],
    "U4": f"""select count(distinct c.lockermat_id_) from reservation_ r
               join lockermat_cell_ c on c.id_ = r.cell_id_ join lockermat_ l on l.id_ = c.lockermat_id_
               where l.status_ = 'ACTIVE' and r.status_ = 'BOOKED' and r.from_ > {T0}
                 and exists (select 1 from access_code_ a where a.reservation_id_ = r.id_ and a.status_ = 'ACTIVE')""",
    "U5": "select count(*) from shipment_",
    "U6": SLICE_QUERIES["expired active codes"],
    "D1": "select count(*) from cell_opening_",
    "D2": """select count(*) from order_ o where exists (select 1 from reservation_ r where r.order_id_ = o.id_)
              and exists (select 1 from payment_ p where p.order_id_ = o.id_)""",
    "D4": SLICE_QUERIES["unreferenced customers"],
    "D6": SLICE_QUERIES["unused lockers"],
    "J1": "select count(*) from audit_event_",
}
ELIGIBLE_CELLS = f"""
    select c.id_, c.lockermat_id_, c.size_
    from lockermat_cell_ c join lockermat_ l on l.id_ = c.lockermat_id_
    where c.status_ = 'IN_SERVICE' and l.status_ = 'ACTIVE'
      and not exists (
          select 1 from reservation_ r where r.cell_id_ = c.id_ and (
              (r.status_ = 'OCCUPIED' and r.to_ <= {T0})
              or (r.status_ in ('BOOKED','OCCUPIED') and r.from_ < {T0} + to_hours(?)
                  and r.to_ > {T0} + to_hours(?))
          )
      )
"""
PERSON_CANDIDATES = """
    select count(*), count(*) filter (where kind = 'CUSTOMER'), count(*) filter (where kind = 'RECIPIENT')
    from (
        select json_extract_string(actor_, '$.kind') as kind,
            coalesce(json_extract_string(actor_, '$.email'), json_extract_string(actor_, '$.phone')) as identity_
        from audit_event_ where json_extract_string(actor_, '$.kind') in ('CUSTOMER', 'RECIPIENT')
        group by all having count(*) > 1
    )
"""


def read_ops(path):
    ops = yaml.safe_load(path.read_text())
    if set(ops) != SCENARIOS:
        raise ValueError(f"Scenario registry mismatch: {sorted(set(ops) ^ SCENARIOS)}")
    for scenario, config in ops.items():
        for field in ("ops", "ops_xs"):
            count = config[field]
            if count is not None and (type(count) is not int or count <= 0):
                raise ValueError(f"{scenario}: invalid {field}")
    return ops


def check_scenarios(db, profile, path=Path("bench/scenarios/ops.yaml")):
    ops = read_ops(path)
    counts = {key: spec["ops_xs"] if profile.size == "XS" else spec["ops"] for key, spec in ops.items()}
    for key, query in COUNTS.items():
        enough(key, scalar(db, query), counts[key])

    check_inserts(db, counts, ops)
    check_reads(db, profile, counts, ops)
    check_retention(db, ops)
    check_json(db, counts)
    print(f"{profile.size}: all {len(ops)} scenario preconditions passed")


def enough(scenario, found, wanted):
    required = 1 if wanted is None else wanted
    if found < required:
        raise ValueError(f"{scenario}: need {required} eligible values, found {found}")


def scalar(db, sql, parameters=None):
    return db.execute(sql, parameters or []).fetchone()[0]


def free_cells(db, config):
    hours = config["days_after_t0"] * 24
    return db.execute(ELIGIBLE_CELLS, [hours + config["window_hours"], hours]).fetchall()


def check_inserts(db, counts, ops):
    key_count, unique_keys, max_id = db.execute("select count(*), count(distinct keycloak_id_), max(id_) from customer_").fetchone()
    if key_count != unique_keys or max_id + counts["C1"] + counts["C5"] >= 2 ** 63:
        raise ValueError("C1/C5: fresh ids and unique existing customer keys required")
    enough("C5", key_count, counts["C5"] // 2)
    enough("C3", len(free_cells(db, ops["C3"])), counts["C3"])
    by_size = {}
    for _, locker, size in free_cells(db, ops["C4"]):
        lockers = by_size.setdefault(size, {})
        lockers[locker] = lockers.get(locker, 0) + 1
    pairs = sum(min(sum(locks.values()) // 2, sum(locks.values()) - max(locks.values())) for locks in by_size.values())
    enough("C4", pairs, counts["C4"])

    candidate_orders = db.execute(f"""
        select distinct r.order_id_ from access_code_ a join reservation_ r on r.id_ = a.reservation_id_
        where a.status_ = 'ACTIVE' and a.valid_from_ <= {T0}
          and a.valid_to_ > {T0} + to_milliseconds(?) order by r.order_id_
    """, [counts["C2"]]).fetchnumpy()["order_id_"]
    enough("C2", len(candidate_orders), 1)
    append_offsets = np.arange(1, counts["C2"] + 1, dtype=np.int64)
    append_orders = candidate_orders[(append_offsets - 1) % len(candidate_orders)]
    pairs_c2 = np.rec.fromarrays((append_orders, append_offsets))
    enough("C2 distinct (order, requested_at)", len(np.unique(pairs_c2)), counts["C2"])
    c6, distinct = db.execute(f"""
        select count(*), count(distinct (r.order_id_, {T0})) from reservation_ r
        join order_ o on o.id_ = r.order_id_ join tariff_ t on t.id_ = o.tariff_id_
        where r.status_ = 'OCCUPIED' and r.to_ < {T0} and t.overstay_price_per_day_ > 0
    """).fetchone()
    enough("C6", c6, None)
    enough("C6 distinct (order, created_at)", distinct, c6)


def check_reads(db, profile, counts, ops):
    r2 = ops["R2"]
    customers = scalar(db, "select count(*) from (select customer_id_ from order_ group by 1 having count(*) >= ?)",
                       [r2["page"] * r2["page_size"]])
    enough("R2", customers, 1)

    r3 = ops["R3"]
    eligible_ids = {locker for _, locker, size in free_cells(db, r3) if size == r3["size"]}
    locations = [WKB_POINT.unpack(point)[-2:] for identifier, point in db.execute(
        "select id_, location_ from lockermat_ order by id_").fetchall() if identifier in eligible_ids]
    safe = geo_points(locations, profile.rng(4), counts["R3"], r3["radius_m"], r3["limit"])
    enough("R3 stable geo points", len(safe), counts["R3"])

    enough("R5", scalar(db, f"""select count(*) from order_ where status_ = 'COMPLETED'
                               and created_at_ >= {T0} - to_days(?) and created_at_ < {T0}""", [ops["R5"]["days"]]), 1)
    enough("R6 months", scalar(db, f"""
        select count(distinct date_trunc('month', p.created_at_)) from payment_ p
        where p.status_ = 'COMPLETED' and p.created_at_ >= date_trunc('month', {T0}) - interval '12 months'
          and p.created_at_ < date_trunc('month', {T0})
          and exists (select 1 from reservation_ r where r.order_id_ = p.order_id_ and r.leg_ in ('STORAGE','ORIGIN'))
    """), counts["R6"])
    enough("R7 days", scalar(db, f"""
        select count(distinct date_trunc('day', requested_at_)) from cell_opening_
        where access_code_id_ is not null and requested_at_ >= {T0} - interval '30 days' and requested_at_ < {T0}
    """), counts["R7"])
    enough("R8 origins", scalar(db, f"""
        select count(distinct roc.lockermat_id_)
        from shipment_ s join order_ o on o.id_ = s.order_id_
        join reservation_ r on r.order_id_ = o.id_ and r.leg_ = 'ORIGIN'
        join reservation_ d on d.order_id_ = o.id_ and d.leg_ = 'DESTINATION'
        join lockermat_cell_ roc on roc.id_ = r.cell_id_
        join lockermat_cell_ dec on dec.id_ = d.cell_id_
        where o.created_at_ >= {T0} - to_days(?) and roc.lockermat_id_ != dec.lockermat_id_
    """, [ops["R8"]["days"]]), counts["R8"])


def geo_points(locations, rng, count, radius, limit):
    locations = np.asarray(locations)
    points = []
    seen = set()
    if not len(locations):
        return points
    lng, lat = np.radians(locations).T
    for _ in range(count * 30):
        point = tuple(np.round(locations[rng.integers(len(locations))] + rng.uniform(-0.01, 0.01, 2), 6))
        if point in seen:
            continue
        seen.add(point)
        p_lng, p_lat = np.radians(point)
        a = np.sin((lat - p_lat) / 2) ** 2 + np.cos(lat) * np.cos(p_lat) * np.sin((lng - p_lng) / 2) ** 2
        distance = 12_742_000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        if np.any(abs(distance - radius) <= radius * 0.01):
            continue
        within = np.sort(distance[distance <= radius])
        if not len(within) or (len(within) > limit and within[limit] < within[limit - 1] * 1.01):
            continue
        points.append(point)
        if len(points) == count:
            break
    return points


def check_retention(db, ops):
    enough("D3", scalar(db, f"select count(*) from cell_opening_ where requested_at_ < {T0} - to_days(?)",
                        [ops["D3"]["cutoff_days"]]), None)
    enough("D5", scalar(db, f"""select count(*) from order_ where status_ in ('CANCELLED','EXPIRED')
                               and created_at_ < {T0} - to_years(?)""", [ops["D5"]["cutoff_years"]]), None)
    enough("J6", scalar(db, f"select count(*) from audit_event_ where entity_ != 'PAYMENT' and at_ < {T0} - to_months(?)",
                        [ops["J6"]["cutoff_months"]]), None)


def check_json(db, counts):
    persons, customers, recipients = db.execute(PERSON_CANDIDATES).fetchone()
    enough("J2", persons, counts["J2"])
    enough("J5", persons, counts["J5"])
    enough("J3 customers with repeated events", customers, 1)
    enough("J3 recipients with repeated events", recipients, 1)
    enough("J4 months", scalar(db, f"""
        select count(distinct date_trunc('month', a.at_))
        from audit_event_ a, json_each(a.changes_) c
        where a.at_ >= date_trunc('month', {T0}) - interval '12 months' and a.at_ < date_trunc('month', {T0})
          and json_extract_string(c.value, '$.f') = 'status_' and json_extract_string(c.value, '$.new') = 'CANCELLED'
    """), counts["J4"])
