import json
import re
from pathlib import Path

import pytest

from bench.scenarios.normalise import digest, result
from bench.scenarios.params import dataset
from bench.scenarios.registry import load

REGISTRY = load()
APPEND = REGISTRY["J1"]
PERSON = REGISTRY["J2"]
KINDS = REGISTRY["J3"]
JX1 = json.loads(Path("docs/bench/indexes.yaml").read_text())["idx"]["JX1"]["engines"]
EXPECTED_PERSON = """
select id_, at_, entity_, entity_id_, action_, actor_, changes_
from audit_event_
where json_extract_string(actor_, '$.email') = $email or json_extract_string(actor_, '$.phone') = $phone
order by at_, id_
"""
EXPECTED_KINDS = """
select json_extract_string(actor_, '$.kind'), count(*),
       count(*) filter (where json_exists(actor_, '$.email')),
       count(*) filter (where (json_exists(actor_, '$.name') or json_exists(actor_, '$.phone'))
                          and not json_exists(actor_, '$.email'))
from audit_event_
group by 1
"""


def expected(scenario, size, params, query):
    kinds = [kind for _, kind in scenario.columns]
    with dataset(size) as (db, _):
        found = [db.execute(query, parameter or None).fetchall() for parameter in params]
    return found, digest([result(kinds, rows, scenario.ordered) for rows in found])


def compact(text):
    return re.sub(r"\s+", "", text).lower()


@pytest.mark.parametrize("scenario", [PERSON], ids=["J2"])
def test_person_events_equal_duckdb_answer(scenario, bench, size):
    params = bench.params[scenario.id]
    _, answer = expected(scenario, size, params, EXPECTED_PERSON)
    assert any(parameter["email"] and parameter["phone"] for parameter in params), "no customer with e-mail and phone"
    assert any(parameter["email"] is None for parameter in params), "no recipient found by phone"
    for engine in scenario.engines:
        for config in scenario.configs:
            assert bench.runs[(scenario.id, engine, config)].hash == answer, f"{engine}/{config}"


@pytest.mark.parametrize("scenario", [KINDS], ids=["J3"])
def test_key_counts_equal_duckdb_answer(scenario, bench, size):
    [rows], answer = expected(scenario, size, bench.params[scenario.id], EXPECTED_KINDS)
    assert all(any(row[index] for row in rows) for index in (2, 3)), rows
    for engine in scenario.engines:
        assert bench.runs[(scenario.id, engine, "idx")].hash == answer, engine


@pytest.mark.parametrize("scenario", [PERSON], ids=["J2"])
def test_idx_plan_uses_jx1(scenario, bench, size):
    if size == "XS":
        pytest.skip("plans are checked from S on")
    first = bench.params[scenario.id][0]
    for engine in scenario.engines:
        wanted = {item["name"] for item in JX1[engine] for key, value in first.items() if value and key in item["name"]}
        access = bench.runs[(scenario.id, engine, "idx")].access
        assert wanted and wanted <= set(access["index"]), f"{engine}: {access}"


@pytest.mark.parametrize("scenario", [PERSON], ids=["J2"])
def test_mysql_repeats_jx1_expression(scenario):
    text = compact(scenario.impls["mysql"].text)
    for item in JX1["mysql"]:
        assert compact(item["keys"][0]) in text, item["name"]


@pytest.mark.parametrize("scenario", [APPEND], ids=["J1"])
def test_mysql_writes_changes_new(scenario, bench):
    count = sum(len(batch) for batch in bench.params[scenario.id])
    for config in scenario.configs:
        assert bench.runs[(scenario.id, "mysql", config)].after == {"rows": count, "wrong": 0}, config
