import json

from bench.analysis.h1 import CONFIRMED, READS, REJECTED, cells, engines, plan_key, served, verdicts
from bench.scenarios.catalogue import H1, INDEXES

PLAN = json.loads(INDEXES.read_text())["idx"]


def cell(engine, config, scenario, seconds, statuses=("ok", "ok", "ok")):
    entry = {"engine": engine, "config": config, "scenario": scenario, "qhash": f"q-{scenario}",
             "state_id": f"s-{engine}-{config}", "seconds": list(seconds), "statuses": list(statuses)}
    if list(statuses) == ["ok"] * 3:
        return entry | {"state": "complete", "mean": sum(seconds) / 3}
    return entry | {"state": "censored"}


def holding(size="L"):
    found, plans = [], {}
    for kind, scenarios in H1.items():
        for scenario in scenarios:
            for engine in engines(scenario):
                idx, base = (1.0, 2.0) if kind == READS else (2.0, 1.0)
                found += [cell(engine, "idx", scenario, [idx] * 3), cell(engine, "base", scenario, [base] * 3)]
                if kind == READS:
                    plans[plan_key(size, found[-2])] = served(PLAN, scenario, engine)
                    plans[plan_key(size, found[-1])] = set()
    return {size: {"cells": found}}, plans


def replace(qa, engine, config, scenario, *args):
    found = qa["L"]["cells"]
    position = next(i for i, entry in enumerate(found) if (entry["engine"], entry["config"], entry["scenario"]) == (engine, config, scenario))
    found[position] = cell(engine, config, scenario, *args)


def entry(qa, plans, scenario, engine, size="L"):
    return next(item for item in cells(qa, plans, PLAN)
                if (item["scenario"], item["engine"], item["size"]) == (scenario, engine, size))


def test_a_faster_read_holds():
    qa, plans = holding()
    found = entry(qa, plans, "R4", "pg")
    assert (found["ratio"], found["direction"], found["plan"], found["holds"]) == (0.5, "faster", True, True)


def test_a_slower_write_holds():
    qa, plans = holding()
    found = entry(qa, plans, "C2", "neo4j")
    assert (found["ratio"], found["direction"], found["holds"]) == (2.0, "slower", True)


def test_equal_means_do_not_hold():
    qa, plans = holding()
    replace(qa, "pg", "idx", "R5", [2.0] * 3)
    replace(qa, "pg", "idx", "U1", [1.0] * 3)
    assert [(found["direction"], found["holds"]) for found in (entry(qa, plans, "R5", "pg"), entry(qa, plans, "U1", "pg"))] == [
        ("equal", False), ("equal", False)]


def test_a_faster_read_without_the_index_does_not_hold():
    qa, plans = holding()
    plans["R6-mysql-idx-L-q-R6-s-mysql-idx.json"] = {"payment__pkey"}
    found = entry(qa, plans, "R6", "mysql")
    assert (found["direction"], found["plan"], found["holds"]) == ("faster", False, False)


def test_a_base_read_timeout_holds():
    qa, plans = holding()
    replace(qa, "mongo", "base", "J2", [600.3, None, None], ("timeout", "skipped", "skipped"))
    replace(qa, "mongo", "idx", "J2", [300.0] * 3)
    found = entry(qa, plans, "J2", "mongo")
    assert (found["base_censored"], found["ratio"], found["direction"], found["holds"]) == (True, None, "faster", True)
    assert found["base_seconds"] == [600.3, None, None]


def test_a_base_write_timeout_does_not_hold():
    qa, plans = holding()
    replace(qa, "pg", "base", "C6", [1.0, 600.1, None], ("ok", "timeout", "skipped"))
    found = entry(qa, plans, "C6", "pg")
    assert (found["base_censored"], found["ratio"], found["direction"], found["holds"]) == (True, None, "faster", False)


def test_every_cell_holding_confirms():
    qa, plans = holding()
    found = verdicts(cells(qa, plans, PLAN))
    assert {name: value["verdict"] for name, value in found.items()} == {
        "pg": CONFIRMED, "mysql": CONFIRMED, "mongo": CONFIRMED, "neo4j": CONFIRMED, "overall": CONFIRMED}


def test_a_failing_cell_rejects_its_engine_and_overall():
    qa, plans = holding()
    replace(qa, "neo4j", "idx", "U5", [0.5] * 3)
    replace(qa, "neo4j", "idx", "R7", [3.0] * 3)
    found = verdicts(cells(qa, plans, PLAN))
    assert found["neo4j"] == {"verdict": REJECTED, "failing": ["R7 neo4j", "U5 neo4j"]}
    assert found["overall"] == {"verdict": REJECTED, "engines": ["neo4j"], "failing": ["R7 neo4j", "U5 neo4j"]}
    assert found["pg"]["verdict"] == CONFIRMED


def test_no_l_cells_give_no_verdict():
    qa, plans = holding("S")
    assert {value["verdict"] for value in verdicts(cells(qa, plans, PLAN)).values()} == {None}


def test_one_missing_l_cell_gives_no_verdict():
    qa, plans = holding()
    qa["L"]["cells"] = [item for item in qa["L"]["cells"] if (item["engine"], item["config"], item["scenario"]) != ("mongo", "base", "J1")]
    found = verdicts(cells(qa, plans, PLAN))
    assert (found["mongo"]["verdict"], found["overall"]["verdict"], found["pg"]["verdict"]) == (None, None, CONFIRMED)


def test_one_missing_plan_file_at_l_gives_no_verdict():
    qa, plans = holding()
    del plans["R5-neo4j-base-L-q-R5-s-neo4j-base.json"]
    found = verdicts(cells(qa, plans, PLAN))
    assert (found["neo4j"]["verdict"], found["overall"]["verdict"], found["mysql"]["verdict"]) == (None, None, CONFIRMED)
