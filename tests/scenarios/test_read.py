from collections import defaultdict

import numpy as np
import pytest

from bench.check.verify.canonical import grosze
from bench.gen.static import WKB_POINT
from bench.scenarios.normalise import digest, result
from bench.scenarios.params import dataset, parameters
from bench.scenarios.registry import load

REGISTRY = load()
DETAIL = REGISTRY["R1"]
PAGE = REGISTRY["R2"]
NEARBY = REGISTRY["R3"]
INCOMING = REGISTRY["R4"]
RANKING = REGISTRY["R5"]
REVENUE = REGISTRY["R6"]
DOORS = REGISTRY["R7"]
REACH = REGISTRY["R8"]
EARTH_METRES = 6_371_000
MARGIN = 0.01
FREE_LOCKERS = """
    select distinct l.id_, l.location_
    from lockermat_ l join lockermat_cell_ c on c.lockermat_id_ = l.id_
    where l.status_ = 'ACTIVE' and c.status_ = 'IN_SERVICE' and c.size_ = $size
      and not exists (select 1 from reservation_ r where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                      and r.from_ < $to and r.to_ > $from)
      and not exists (select 1 from reservation_ r where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED'
                      and r.to_ <= $now)
    order by 1
"""
SHIP_LINKS = """
    select o.lockermat_id_, d.lockermat_id_
    from shipment_ s
    join order_ x on x.id_ = s.order_id_
    join (select r.order_id_, c.lockermat_id_ from reservation_ r join lockermat_cell_ c on c.id_ = r.cell_id_
          where r.leg_ = 'ORIGIN') o on o.order_id_ = s.order_id_
    join (select r.order_id_, c.lockermat_id_ from reservation_ r join lockermat_cell_ c on c.id_ = r.cell_id_
          where r.leg_ = 'DESTINATION') d on d.order_id_ = s.order_id_
    where x.created_at_ >= ?
"""
EXPECTED_RANKING = """
    select c.lockermat_id_, count(*) as n
    from order_ o join reservation_ r on r.order_id_ = o.id_ join lockermat_cell_ c on c.id_ = r.cell_id_
    where o.status_ = 'COMPLETED' and r.leg_ in ('STORAGE', 'ORIGIN') and o.{column} >= $since and o.{column} < $now
    group by 1 order by n desc, 1 limit $limit
"""
CREATED_BEFORE_COMPLETED_INSIDE = """
    select count(*) from order_
    where status_ = 'COMPLETED' and created_at_ < $since and closed_at_ >= $since and closed_at_ < $now
"""
LEDGER = """
    select coalesce(sum(case when kind_ in ('REFUND', 'COMPENSATION') then -amount_ else amount_ end), 0)
    from payment_ where status_ = 'COMPLETED' and created_at_ >= $since and created_at_ < $until
"""
EXPECTED_REVENUE = """
    select c.lockermat_id_, sum(case when p.kind_ in ('REFUND', 'COMPENSATION') then -p.amount_ else p.amount_ end)
    from payment_ p
    join order_ o on o.id_ = p.order_id_
    join reservation_ r on r.order_id_ = o.id_
        and r.leg_ = case o.type_ when 'SHIPMENT' then 'ORIGIN' else 'STORAGE' end
    join lockermat_cell_ c on c.id_ = r.cell_id_
    where p.status_ = 'COMPLETED' and p.created_at_ >= $since and p.created_at_ < $until
    group by 1
"""
REFUNDED_SHIPMENTS = """
    select count(distinct p.order_id_)
    from payment_ p
    join reservation_ a on a.order_id_ = p.order_id_ and a.leg_ = 'ORIGIN'
    join reservation_ b on b.order_id_ = p.order_id_ and b.leg_ = 'DESTINATION'
    join lockermat_cell_ x on x.id_ = a.cell_id_
    join lockermat_cell_ y on y.id_ = b.cell_id_
    where p.kind_ = 'REFUND' and p.status_ = 'COMPLETED' and x.lockermat_id_ <> y.lockermat_id_
      and p.created_at_ >= $since and p.created_at_ < $until
"""
EXPECTED_DOORS = """
    select c.lockermat_id_, count(*), count(*) filter (where o.result_ = 'DOOR_FAILED')
    from cell_opening_ o
    join access_code_ a on a.id_ = o.access_code_id_
    join reservation_ r on r.id_ = a.reservation_id_
    join lockermat_cell_ c on c.id_ = r.cell_id_
    where o.requested_at_ >= $since and o.requested_at_ < $until
    group by 1
"""
SERVICE_OPENINGS = """
    select count(*) from cell_opening_
    where channel_ = 'SERVICE' and requested_at_ >= $since and requested_at_ < $until
"""
LOCKER_FIELDS = ("lockermat_id", "lockermat_name", "lockermat_address")
EXPECTED_ORDERS = """
    select id_, number_, type_, status_, price_, epoch_ms(created_at_)
    from order_ where id_ in (select unnest(?))
"""
EXPECTED_LEGS = """
    select r.order_id_, r.id_, r.leg_, r.status_, epoch_ms(r.from_), epoch_ms(r.to_), c.lockermat_id_, l.name_, l.address_
    from reservation_ r join lockermat_cell_ c on c.id_ = r.cell_id_ join lockermat_ l on l.id_ = c.lockermat_id_
    where r.order_id_ in (select unnest(?))
"""
EXPECTED_CODES = """
    select reservation_id_, id_, purpose_, status_, epoch_ms(valid_from_), epoch_ms(valid_to_)
    from access_code_ where reservation_id_ in (select id_ from reservation_ where order_id_ in (select unnest(?)))
"""
EXPECTED_PAYMENTS = """
    select order_id_, id_, kind_, status_, amount_, epoch_ms(created_at_)
    from payment_ where order_id_ in (select unnest(?))
"""


def grouped(db, query, ids):
    found = defaultdict(list)
    for parent, *values in db.execute(query, [ids]).fetchall():
        found[parent].append(values)
    return found


def expected_detail(size, params):
    ids = [parameter["order"] for parameter in params]
    with dataset(size) as (db, _):
        orders = {values[0]: values for values in db.execute(EXPECTED_ORDERS, [ids]).fetchall()}
        legs = grouped(db, EXPECTED_LEGS, ids)
        codes = grouped(db, EXPECTED_CODES, ids)
        payments = grouped(db, EXPECTED_PAYMENTS, ids)
    kinds = [kind for _, kind in DETAIL.columns]
    answer = []
    for order in ids:
        head = list(orders[order])
        rows = [head + leg + code + [None] * 5 for leg in legs[order] for code in codes[leg[0]] or [[None] * 5]]
        rows += [head + [None] * 13 + payment for payment in payments[order]]
        answer.append(result(kinds, rows, False))
    return digest(answer)


@pytest.mark.parametrize("scenario", [DETAIL], ids=["R1"])
def test_detail_equals_duckdb_answer(scenario, bench, size):
    expected = expected_detail(size, bench.params[scenario.id])
    for engine in scenario.engines:
        assert bench.runs[(scenario.id, engine, "idx")].hash == expected, engine


@pytest.mark.parametrize("scenario", [DETAIL], ids=["R1"])
def test_detail_returns_frozen_fields(scenario, bench):
    names = [name for name, _ in scenario.columns]
    assert set(LOCKER_FIELDS) <= set(names)
    for engine in scenario.engines:
        rows = [row for found in bench.runs[(scenario.id, engine, "idx")].outcome.results for row in found]
        assert rows and {len(row) for row in rows} == {len(names)}, engine


@pytest.mark.parametrize("scenario", [PAGE], ids=["R2"])
def test_page_has_twenty_rows(scenario, bench, size):
    expected = [scenario.config(size)["page_size"]] * len(bench.params[scenario.id])
    assert expected[0] == 20
    for engine in scenario.engines:
        assert [len(rows) for rows in bench.runs[(scenario.id, engine, "idx")].results] == expected, engine


def free_lockers(size, params):
    windows = {(parameter["size"], parameter["from"], parameter["to"], parameter["now"]) for parameter in params}
    assert len(windows) == 1
    [(cell_size, start, end, now)] = windows
    with dataset(size) as (db, _):
        rows = db.execute(FREE_LOCKERS, {"size": cell_size, "from": start, "to": end, "now": now}).fetchall()
    locations = np.radians([WKB_POINT.unpack(point)[-2:] for _, point in rows]).T
    return np.array([identifier for identifier, _ in rows]), locations


def distances(lockers, parameter):
    lng, lat = lockers
    p_lng, p_lat = np.radians([parameter["lng"], parameter["lat"]])
    a = np.sin((lat - p_lat) / 2) ** 2 + np.cos(lat) * np.cos(p_lat) * np.sin((lng - p_lng) / 2) ** 2
    return 2 * EARTH_METRES * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


@pytest.mark.parametrize("scenario", [NEARBY], ids=["R3"])
def test_geo_parameters_keep_the_margins(scenario, size):
    with dataset(size) as (db, profile):
        params = parameters(scenario, db, profile)
    ids, lockers = free_lockers(size, params)
    assert len(params) == scenario.config(size)["count"]
    for index, parameter in enumerate(params):
        radius, limit = parameter["radius"], parameter["limit"]
        distance = distances(lockers, parameter)
        assert not np.any(abs(distance - radius) <= radius * MARGIN), f"set {index}: a locker lies at the radius"
        within = np.sort(distance[distance <= radius])
        assert len(within), f"set {index}: no free locker within the radius"
        if len(within) > limit:
            assert within[limit] >= within[limit - 1] * (1 + MARGIN), f"set {index}: places {limit} and {limit + 1} tie"


@pytest.mark.parametrize("scenario", [NEARBY], ids=["R3"])
def test_nearest_lockers_equal_haversine_answer(scenario, bench, size):
    params = bench.params[scenario.id]
    ids, lockers = free_lockers(size, params)
    expected = []
    for parameter in params:
        distance = distances(lockers, parameter)
        nearest = [index for index in np.argsort(distance)[:parameter["limit"]]
                   if distance[index] <= parameter["radius"]]
        expected.append({int(ids[index]): float(distance[index]) for index in nearest})
    for engine in scenario.engines:
        run = bench.runs[(scenario.id, engine, "idx")]
        assert run.error is None, f"{engine}: {run.error}"
        for index, (rows, wanted) in enumerate(zip(run.outcome.results, expected, strict=True)):
            found = {int(identifier): float(metres) for identifier, metres in rows}
            assert found.keys() == wanted.keys(), f"{engine} set {index}"
            assert all(abs(found[key] - wanted[key]) <= wanted[key] * MARGIN for key in wanted), \
                f"{engine} set {index}: {found} vs {wanted}"


def breadth_first(links, start, max_hops):
    hops = {start: 0}
    frontier = {start}
    for level in range(1, max_hops + 1):
        frontier = {target for origin in frontier for target in links.get(origin, ())} - hops.keys()
        hops |= dict.fromkeys(frontier, level)
    del hops[start]
    return hops


@pytest.mark.parametrize("scenario", [REACH], ids=["R8"])
def test_reach_equals_breadth_first_answer(scenario, bench, size):
    params = bench.params[scenario.id]
    with dataset(size) as (db, _):
        links = defaultdict(set)
        for origin, destination in db.execute(SHIP_LINKS, [params[0]["since"]]).fetchall():
            links[origin].add(destination)
    kinds = [kind for _, kind in scenario.columns]
    answer = digest([result(kinds, list(breadth_first(links, parameter["lockermat"], parameter["max_hops"]).items()),
                            False) for parameter in params])
    for engine in scenario.engines:
        assert bench.runs[(scenario.id, engine, "idx")].hash == answer, engine


@pytest.mark.parametrize("scenario", [REACH], ids=["R8"])
def test_reach_frontier_seeks_from_at_index(scenario, bench):
    access = bench.runs[(scenario.id, "mongo", "idx")].access
    assert "IXSCAN" in access["access_path"] and access["index"] == ["shiplinks_from_at__idx"], access


def ranking(db, parameter, column):
    found = db.execute(EXPECTED_RANKING.format(column=column), parameter).fetchall()
    return digest([result([kind for _, kind in RANKING.columns], found, True)])


@pytest.mark.parametrize("scenario", [RANKING], ids=["R5"])
def test_ranking_equals_duckdb_answer(scenario, bench, size):
    [parameter] = bench.params[scenario.id]
    with dataset(size) as (db, _):
        [(outside,)] = db.execute(CREATED_BEFORE_COMPLETED_INSIDE, {key: parameter[key] for key in ("since", "now")}).fetchall()
        expected = ranking(db, parameter, "created_at_")
        by_completion = ranking(db, parameter, "closed_at_")
    assert outside, "no completed order created before the window and closed inside it"
    assert by_completion != expected, "the orders created before the window do not change the ranking"
    for engine in scenario.engines:
        for config in scenario.configs:
            assert bench.runs[(scenario.id, engine, config)].hash == expected, f"{engine}/{config}"


@pytest.mark.parametrize("scenario", [REVENUE], ids=["R6"])
def test_revenue_adds_up_to_the_ledger(scenario, bench, size):
    params = bench.params[scenario.id]
    kinds = [kind for _, kind in scenario.columns]
    with dataset(size) as (db, _):
        ledger = [grosze(db.execute(LEDGER, parameter).fetchone()[0]) for parameter in params]
        refunded = sum(db.execute(REFUNDED_SHIPMENTS, parameter).fetchone()[0] for parameter in params)
        expected = digest([result(kinds, db.execute(EXPECTED_REVENUE, parameter).fetchall(), False)
                           for parameter in params])
    assert refunded, "no refunded two-leg shipment in the measured months"
    for engine in scenario.engines:
        for config in scenario.configs:
            run = bench.runs[(scenario.id, engine, config)]
            assert run.error is None, f"{engine}/{config}: {run.error}"
            assert [sum(net for _, net in rows) for rows in run.results] == ledger, f"{engine}/{config}"
            assert run.hash == expected, f"{engine}/{config}"


@pytest.mark.parametrize("scenario", [DOORS], ids=["R7"])
def test_door_activity_equals_duckdb_answer(scenario, bench, size):
    params = bench.params[scenario.id]
    kinds = [kind for _, kind in scenario.columns]
    with dataset(size) as (db, _):
        found = [db.execute(EXPECTED_DOORS, parameter).fetchall() for parameter in params]
        service = sum(db.execute(SERVICE_OPENINGS, parameter).fetchone()[0] for parameter in params)
    assert service, "no service opening in the measured days"
    assert sum(failed for rows in found for *_, failed in rows), "no failed opening in the measured days"
    expected = digest([result(kinds, rows, False) for rows in found])
    for engine in scenario.engines:
        for config in scenario.configs:
            assert bench.runs[(scenario.id, engine, config)].hash == expected, f"{engine}/{config}"


@pytest.mark.parametrize(("scenario", "index"), [(INCOMING, "ix1__idx"), (RANKING, "ix2__idx"), (REVENUE, "ix3__idx"),
                                                 (DOORS, "ix4__idx")], ids=["R4", "R5", "R6", "R7"])
def test_idx_plan_uses_added_index(scenario, index, bench, size):
    if size == "XS":
        pytest.skip("plans are checked from S on")
    access = bench.runs[(scenario.id, "pg", "idx")].access
    assert index in access["index"], access
