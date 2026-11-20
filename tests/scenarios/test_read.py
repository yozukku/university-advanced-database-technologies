from collections import defaultdict

import pytest

from bench.scenarios.normalise import digest, result
from bench.scenarios.params import dataset
from bench.scenarios.registry import load

REGISTRY = load()
DETAIL = REGISTRY["R1"]
PAGE = REGISTRY["R2"]
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
