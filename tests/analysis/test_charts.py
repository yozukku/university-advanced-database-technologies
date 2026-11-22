import json

import pytest
from matplotlib.figure import Figure

from bench.analysis import charts


def line(engine, config, run, milliseconds, version="new", status="ok", scenario="R4", size="S"):
    return {"engine": engine, "size": size, "config": config, "scenario": scenario, "run": run, "status": status,
            "qhash": f"q-{version}", "state_id": f"s-{version}", "nanoseconds": int(milliseconds * 1e6)}


def write_runs(directory, lines):
    (directory / "runs.jsonl").write_text("".join(json.dumps(item) + "\n" for item in lines))


def heights(figure):
    return [patch.get_height() for axes in figure.axes for patch in axes.patches]


def test_polish_number_format():
    assert charts.polish(1234.5) == "1 234,5"
    assert charts.polish(1000) == "1 000"
    assert charts.polish(0.25) == "0,25"


@pytest.mark.parametrize(("slowest", "log"), [(50, True), (49, False)])
def test_log_axis_from_a_max_min_ratio_of_50_and_its_caption(slowest, log):
    cells = {("pg", "S", "idx", "R1"): [1, 1, 1], ("mysql", "S", "idx", "R1"): [slowest] * 3}
    figure, caption = charts.scenario_chart(cells, "R1")
    axes = figure.axes[0]
    assert axes.get_yscale() == ("log" if log else "linear")
    assert (charts.LOG_NOTE in caption) is log
    assert (charts.LOG_NOTE in axes.get_ylabel()) is log


def test_a_value_axis_without_unit_fails(tmp_path):
    figure = Figure()
    figure.add_subplot().set_ylabel("Czas")
    with pytest.raises(ValueError):
        charts.save(figure, tmp_path / "x.png")
    assert not (tmp_path / "x.png").exists()


def test_the_chart_of_a_ba_scenario_reads_exactly_the_three_current_idx_lines(tmp_path):
    write_runs(tmp_path, [
        *(line("pg", "idx", run, 100, version="old") for run in (1, 2, 3)),
        *(line("pg", "base", run, 500) for run in (1, 2, 3)),
        *(line("pg", "idx", run, milliseconds) for run, milliseconds in ((1, 10), (2, 20), (3, 30))),
        line("mysql", "idx", 1, 15), line("mysql", "idx", 2, 15), line("mysql", "idx", 3, 600000, status="timeout"),
        *(line("mongo", "idx", run, 40, version="old") for run in (1, 2, 3)),
        *(line("mongo", "idx", run, 40) for run in (1, 2)),
    ])
    cells = charts.complete(tmp_path)
    assert cells == {("pg", "S", "idx", "R4"): [10, 20, 30], ("pg", "S", "base", "R4"): [500, 500, 500]}
    figure, _ = charts.scenario_chart(cells, "R4")
    assert heights(figure) == [20]
    captions = charts.write(tmp_path)
    assert sorted(captions) == ["R4", "R4-ba", "heatmap-S"]
    assert (tmp_path / "charts" / "R4.png").is_file() and (tmp_path / "charts" / "R4-ba.png").is_file()


def test_the_h1_chart_reads_the_l_cells_of_h1_json(tmp_path):
    cells = [{"set": "H1-S", "scenario": "R4", "engine": "pg", "size": size, "ratio": 0.1, "holds": True}
             for size in ("S", "L")] + [{"set": "H1-I", "scenario": "C3", "engine": "mysql", "size": "L", "ratio": 0.95,
                                         "holds": False}]
    (tmp_path / "h1.json").write_text(json.dumps({"cells": cells, "verdicts": {}}))
    assert "h1-L" in charts.write(tmp_path)
    figure, caption = charts.h1_chart([cell for cell in cells if cell["size"] == "L"], "L")
    assert figure.axes[0].get_yscale() == "log" and charts.LOG_NOTE in caption
    assert [len(collection.get_offsets()) for collection in figure.axes[0].collections] == [1, 1]
