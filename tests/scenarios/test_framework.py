import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from neo4j.time import DateTime

from bench.scenarios.explain import access
from bench.scenarios.normalise import digest, result
from bench.scenarios.oracle import affected, compare, diff
from bench.scenarios.params import child_id, dataset, fresh_id, parameters, seed
from bench.scenarios.qhash import qhash
from bench.scenarios.registry import load
from trial import CANCEL, COUNT, PURGE, sample

PLANS = Path(__file__).parent / "plans"
SCHEMA = {"reservation_": [("id_", "int"), ("leg_", "text"), ("status_", "text")]}


def qhashes(size, scenarios):
    with dataset(size) as (db, profile):
        return {scenario.id: qhash(scenario, profile, parameters(scenario, db, profile)) for scenario in scenarios}


def heaviest_first(pick):
    return sample(pick, "select distinct customer_id_ from order_ order by 1 desc", "customer")


def test_count_changes_only_its_qhash(size):
    scenarios = [*load().values(), COUNT, CANCEL, PURGE]
    before = qhashes(size, scenarios)
    changed = replace(CANCEL, ops=CANCEL.ops | {"ops": CANCEL.ops["ops"] + 1, "ops_xs": CANCEL.ops["ops_xs"] + 1})
    after = qhashes(size, [changed if scenario is CANCEL else scenario for scenario in scenarios])
    assert [key for key in before if before[key] != after[key]] == [CANCEL.id]


def test_selector_changes_only_its_qhash(size):
    scenarios = [*load().values(), COUNT, CANCEL, PURGE]
    corrected = replace(COUNT, select=heaviest_first)
    with dataset(size) as (db, profile):
        assert parameters(corrected, db, profile) != parameters(COUNT, db, profile)
        assert seed(profile, corrected) == seed(profile, COUNT)
    before = qhashes(size, scenarios)
    after = qhashes(size, [corrected if scenario is COUNT else scenario for scenario in scenarios])
    assert [key for key in before if before[key] != after[key]] == [COUNT.id]


def test_parameters_repeat(size):
    with dataset(size) as (db, profile):
        assert parameters(COUNT, db, profile) == parameters(COUNT, db, profile)


def test_normaliser_parses_json_and_units():
    kinds = ["json", "grosze", "ms"]
    moment = datetime(2026, 11, 1, 12, 30, 0, 123000, tzinfo=timezone.utc)
    relational = [('{"kind": "CUSTOMER", "email": "a@b.pl"}', Decimal("15.20"), moment)]
    document = [({"email": "a@b.pl", "kind": "CUSTOMER"}, 1520, moment.replace(tzinfo=None))]
    graph = [('{"email":"a@b.pl","kind":"CUSTOMER"}', 1520, DateTime.from_native(moment))]
    assert digest(result(kinds, relational, False)) == digest(result(kinds, document, False)) == digest(result(kinds, graph, False))
    assert digest(result(kinds, relational, False)) != digest(result(kinds, [('{"kind": "SYSTEM"}', 1520, moment)], False))


def test_unordered_results_ignore_row_order():
    rows = [("PAID", 2), ("COMPLETED", 5)]
    assert result(["text", "int"], rows, False) == result(["text", "int"], rows[::-1], False)
    assert result(["text", "int"], rows, True) != result(["text", "int"], rows[::-1], True)


def test_ids_derive_from_the_parent():
    assert child_id(1234, 0) == 10_000_000_001_234
    assert child_id(fresh_id(7), 2) == 31_000_000_000_007
    assert len({child_id(parent, slot) for parent in (1, 2, fresh_id(1)) for slot in range(3)}) == 9


def test_diff_finds_the_wrong_leg():
    before = {"reservation_": {1: '[1,"ORIGIN","BOOKED"]', 2: '[2,"DESTINATION","BOOKED"]'}}
    right = diff(before, {"reservation_": {1: '[1,"ORIGIN","BOOKED"]', 2: '[2,"DESTINATION","CANCELLED"]'}}, SCHEMA)
    wrong = diff(before, {"reservation_": {1: '[1,"ORIGIN","CANCELLED"]', 2: '[2,"DESTINATION","BOOKED"]'}}, SCHEMA)
    assert right["reservation_"]["changed"] == [[2, {"status_": ["BOOKED", "CANCELLED"]}]]
    assert affected(right) == affected(wrong)
    assert compare({"pg": right, "mongo": wrong})


@pytest.mark.parametrize("engine, expected", [
    ("pg", {"access_path": ["Bitmap Heap Scan", "Bitmap Index Scan"], "index": ["order_customer_created__idx"]}),
    ("mysql", {"access_path": ["ref"], "index": ["order_customer_created__idx"]}),
    ("mongo", {"access_path": ["IXSCAN"], "index": ["order_customer_created__idx"]}),
    ("neo4j", {"access_path": ["NodeUniqueIndexSeek"], "index": ["Customer_id__uq"]}),
])
def test_plan_access_path_and_index(engine, expected):
    assert access(engine, json.loads((PLANS / f"{engine}.json").read_text())) == expected


def test_mysql_index_merge_names_each_index():
    found = access("mysql", json.loads((PLANS / "mysql_index_merge.json").read_text()))
    assert found == {"access_path": ["index_merge"], "index": ["jx1_email__idx", "jx1_phone__idx"]}
