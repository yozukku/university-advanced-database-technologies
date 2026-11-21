import pytest

from bench.runner.store import Store

KEY = {"engine": "pg", "size": "XS", "config": "idx", "scenario": "R4", "qhash": "q1", "state_id": "s1"}


def line(run, status="ok", **changed):
    return {**KEY, **changed, "run": run, "status": status, "nanoseconds": 1}


def test_a_restarted_store_skips_finished_runs(tmp_path):
    first = Store(tmp_path)
    first.append(line(1))
    first.append(line(2))
    restarted = Store(tmp_path)
    assert restarted.pending(KEY, (1, 2, 3)) == ([3], False)
    with pytest.raises(RuntimeError):
        restarted.append(line(2))
    assert len((tmp_path / "runs.jsonl").read_text().splitlines()) == 2


def test_another_qhash_or_state_reopens_the_cell(tmp_path):
    store = Store(tmp_path)
    for run in (1, 2, 3):
        store.append(line(run, qhash="old"))
        store.append(line(run, state_id="old"))
    assert store.pending(KEY, (1, 2, 3)) == ([1, 2, 3], False)


def test_a_failed_run_marks_the_cell(tmp_path):
    store = Store(tmp_path)
    store.append(line(1, "timeout"))
    assert store.pending(KEY, (1, 2, 3)) == ([2, 3], True)


def test_forget_removes_only_that_cell(tmp_path):
    store = Store(tmp_path)
    for run in (1, 2, 3):
        store.append(line(run))
        store.append(line(run, config="base"))
        store.append(line(run, scenario="R5"))
    assert store.forget("pg", "XS", "R4") == 6
    assert Store(tmp_path).pending(KEY, (1, 2, 3)) == ([1, 2, 3], False)
    assert [entry["scenario"] for entry in Store(tmp_path).lines] == ["R5"] * 3
