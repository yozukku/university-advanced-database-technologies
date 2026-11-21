import json
import re
from pathlib import Path

import pytest

from bench.scenarios.json.pseudonymise import pseudonym
from bench.scenarios.normalise import digest, result
from bench.scenarios.params import dataset
from bench.scenarios.registry import load

REGISTRY = load()
APPEND = REGISTRY["J1"]
PERSON = REGISTRY["J2"]
KINDS = REGISTRY["J3"]
CHANGES = REGISTRY["J4"]
FORGET = REGISTRY["J5"]
IDX = json.loads(Path("docs/bench/indexes.yaml").read_text())["idx"]
JX1 = IDX["JX1"]["engines"]
JX2 = IDX["JX2"]["engines"]
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
EXPECTED_CHANGES = """
select entity_, count(*)
from audit_event_ a
where at_ >= $since and at_ < $until
  and exists (select 1 from json_each(a.changes_) c
              where json_extract_string(c.value, '$.f') = 'status_' and json_extract_string(c.value, '$.new') = $value)
group by 1
"""
EXPECTED_FORGOTTEN = """
select id_
from audit_event_
where list_contains($emails, json_extract_string(actor_, '$.email'))
   or list_contains($phones, json_extract_string(actor_, '$.phone'))
order by 1
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


@pytest.mark.parametrize("scenario", [PERSON, FORGET], ids=["J2", "J5"])
def test_mysql_repeats_jx1_expression(scenario):
    text = compact(scenario.impls["mysql"].text)
    for item in JX1["mysql"]:
        assert compact(item["keys"][0]) in text, item["name"]


@pytest.mark.parametrize("scenario", [APPEND], ids=["J1"])
def test_mysql_writes_changes_new(scenario, bench):
    count = sum(len(batch) for batch in bench.params[scenario.id])
    for config in scenario.configs:
        assert bench.runs[(scenario.id, "mysql", config)].after == {"rows": count, "wrong": 0}, config


@pytest.mark.parametrize("scenario", [CHANGES], ids=["J4"])
def test_status_counts_equal_duckdb_answer(scenario, bench, size):
    params = bench.params[scenario.id]
    _, answer = expected(scenario, size, params, EXPECTED_CHANGES)
    for engine in scenario.engines:
        for config in scenario.configs:
            assert bench.runs[(scenario.id, engine, config)].hash == answer, f"{engine}/{config}"


@pytest.mark.parametrize("scenario", [CHANGES], ids=["J4"])
def test_idx_plan_uses_jx2(scenario, bench, size):
    if size == "XS":
        pytest.skip("plans are checked from S on")
    for engine in scenario.engines:
        access = bench.runs[(scenario.id, engine, "idx")].access
        assert {item["name"] for item in JX2[engine]} <= set(access["index"]), f"{engine}: {access}"


@pytest.mark.parametrize("scenario", [FORGET], ids=["J5"])
def test_pseudonymised_persons_keep_no_identifier(scenario, bench, size):
    params = bench.params[scenario.id]
    with dataset(size) as (db, _):
        wanted = [found for found, in db.execute(EXPECTED_FORGOTTEN, {key: params[key] for key in ("emails", "phones")})
                  .fetchall()]
    assert wanted, "no event of the chosen persons"
    for engine in scenario.engines:
        for config in scenario.configs:
            run = bench.runs[(scenario.id, engine, config)]
            entry = run.probe["audit_event_"]
            assert not entry["inserted"] and not entry["deleted"], f"{engine}/{config}"
            assert [key for key, _ in entry["changed"]] == wanted, f"{engine}/{config}"
            for key, change in entry["changed"]:
                old, new = change["actor_"]
                assert not {"name", "phone"} & new.keys(), f"{engine}/{config} event {key}: {new}"
                email = pseudonym(params["key"], old["email"]) if "email" in old else None
                assert new.get("email") == email, f"{engine}/{config} event {key}: {new}"
            assert run.after == {"left": 0}, f"{engine}/{config}: {run.after}"
