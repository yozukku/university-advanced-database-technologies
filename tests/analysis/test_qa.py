from types import SimpleNamespace

import pytest

from bench.analysis.qa import check

READ = SimpleNamespace(id="R4", op="R", read=True)
WRITE = SimpleNamespace(id="C2", op="C", read=False)
ENGINES = ("pg", "mysql", "mongo", "neo4j")


def key(scenario, engine, config):
    return {"engine": engine, "size": "XS", "config": config, "scenario": scenario.id, "qhash": "q", "state_id": "s"}


def runs(scenario, engine, config, seconds=(1.0, 1.1, 1.2), statuses=("ok", "ok", "ok")):
    found = {}
    for run, (value, status) in enumerate(zip(seconds, statuses), start=1):
        line = {**key(scenario, engine, config), "run": run, "status": status,
                "nanoseconds": None if value is None else int(value * 1e9)}
        if status == "ok":
            line |= {"rows": 11, "hash": "a" * 64} if scenario.read else {"rows": 1000, "digests": {"cell_opening_": "b" * 64}}
        found[run] = line
    return found


def clean():
    return {(scenario.id, engine, config): runs(scenario, engine, config)
            for scenario in (READ, WRITE) for engine in ENGINES for config in ("idx", "base")}


def report(cells):
    scenarios = {scenario.id: scenario for scenario in (READ, WRITE)}
    return check([(scenarios[scenario], key(scenarios[scenario], engine, config), found)
                  for (scenario, engine, config), found in cells.items()])


def test_clean_data_passes():
    found = report(clean())
    assert found["problems"] == [] and found["warnings"] == []
    assert {cell["state"] for cell in found["cells"]} == {"complete"}


def test_a_hash_mismatch_fails():
    cells = clean()
    cells[("R4", "mongo", "idx")][2]["hash"] = "c" * 64
    assert [problem for problem in report(cells)["problems"] if "hash mismatch" in problem] == [
        "R4: hash mismatch: aaaaaaaaaaaa pg idx, pg base, mysql idx, mysql base, mongo idx, mongo base, neo4j idx, "
        "neo4j base; cccccccccccc mongo idx"]


def test_a_cell_with_two_ok_runs_fails():
    cells = clean()
    del cells[("C2", "neo4j", "idx")][3]
    assert report(cells)["problems"] == ["neo4j idx C2: incomplete (ok, ok, missing)"]


@pytest.mark.parametrize("statuses", [("timeout", "skipped", "skipped"), ("ok", "timeout", "skipped"), ("ok", "ok", "timeout")])
def test_a_base_timeout_is_censored(statuses):
    cells = clean()
    seconds = [600.2 if status == "timeout" else None if status == "skipped" else 1.0 for status in statuses]
    cells[("R4", "pg", "base")] = runs(READ, "pg", "base", seconds, statuses)
    found = report(cells)
    assert found["problems"] == []
    assert [cell["state"] for cell in found["cells"] if cell["config"] == "base" and cell["engine"] == "pg"
            and cell["scenario"] == "R4"] == ["censored"]
    assert found["warnings"] == [f"pg base R4: censored, BASE timed out ({', '.join(statuses)})"]


def test_an_idx_timeout_fails():
    cells = clean()
    cells[("R4", "pg", "idx")] = runs(READ, "pg", "idx", (600.2, None, None), ("timeout", "skipped", "skipped"))
    assert report(cells)["problems"] == ["pg idx R4 run 1: timeout in IDX", "pg idx R4: incomplete (timeout, skipped, skipped)"]


def test_a_high_cv_is_only_a_warning():
    cells = clean()
    cells[("C2", "mysql", "base")] = runs(WRITE, "mysql", "base", (0.6, 1.0, 1.4))
    found = report(cells)
    assert found["problems"] == []
    assert found["warnings"] == ["mysql base C2: CV 40.0% > 15%"]


def test_the_mean_comes_from_the_three_runs():
    cells = clean()
    cells[("R4", "pg", "idx")] = runs(READ, "pg", "idx", (1.0, 2.0, 6.0))
    cell = next(cell for cell in report(cells)["cells"] if (cell["engine"], cell["config"], cell["scenario"]) == ("pg", "idx", "R4"))
    assert (cell["mean"], cell["min"], cell["max"], cell["median"]) == (3.0, 1.0, 6.0, 2.0)
    assert cell["seconds"] == [1.0, 2.0, 6.0]
