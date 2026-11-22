import json
import signal

import pytest

from bench.analysis.steps import durations
from bench.runner import full


def journal(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_failure_in_the_first_size_fails_the_run_after_a_green_second_size(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    calls = []

    def stub(name, size, code=0):
        return full.Step(name, None, lambda: calls.append((size, name)) or code)

    def plan(size):
        return [stub("data", size, 1 if size == "XS" else 0), stub("load", size), stub("qa", size)]

    def finish(directory, out):
        return [stub("h1", None), stub("charts", None), stub("report", None)]

    assert full.run(["XS", "S"], None, plan, finish) == 1
    assert calls == [("XS", "data"), ("XS", "qa"), ("S", "data"), ("S", "load"), ("S", "qa"),
                     (None, "h1"), (None, "charts"), (None, "report")]
    assert [line["exit"] for line in journal(tmp_path / full.JOURNAL)] == [1, 0, 0, 0, 0, 0, 0, 0]


def test_an_interrupted_step_keeps_its_line_and_the_resumed_one_adds_to_it(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    marker = tmp_path / "data.key"

    def interrupted():
        raise full.Interrupted(signal.SIGINT)

    def plan(step):
        return lambda size: [full.Step("data", None, lambda: 0, lambda: "d1", lambda key: marker.exists(), marker),
                             full.Step("bench", "pg", step, lambda: "s1")]

    with pytest.raises(full.Interrupted):
        full.run(["XS"], "bench", plan(interrupted))
    assert full.run(["XS"], "bench", plan(lambda: 0)) == 0
    lines = journal(tmp_path / full.JOURNAL)
    assert [(line["step"], line["exit"]) for line in lines] == [("data", 0), ("bench", 130), ("bench", 0)]
    assert durations(lines)[("XS", "bench", "pg")] == lines[1]["seconds"] + lines[2]["seconds"]
