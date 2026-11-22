import json
from pathlib import Path

from bench.report import indexes
from bench.report.dataset import ENGINES

RESULTS = Path("results")
CHAPTERS = Path("report/chapters")


def rows(markdown):
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in markdown.splitlines()[2:]]


def value(text):
    return float(text.replace(" ", "").replace(",", "."))


def test_h1_tables_equal_h1_json():
    found = json.loads((RESULTS / "h1.json").read_text())
    for size in indexes.SIZES:
        cells = [cell for cell in found["cells"] if cell["size"] == size]
        table = rows(indexes.TABLES[f"h1-{size}"](RESULTS))
        assert len(table) == len(cells) > 0
        for row, cell in zip(table, cells):
            assert row[:3] == [cell["set"], cell["scenario"], ENGINES[cell["engine"]]]
            assert value(row[3]) == round(cell["base_mean"] * 1000, 1)
            assert value(row[4]) == round(cell["idx_mean"] * 1000, 1)
            assert abs(value(row[5]) / cell["ratio"] - 1) < 0.01
            assert row[6] == {"faster": "szybciej", "slower": "wolniej", "equal": "bez zmian"}[cell["direction"]]
            assert row[7:] == [{True: "tak", False: "nie", None: "—"}[cell[key]] for key in ("plan", "holds")]


def test_verdict_table_equals_h1_json():
    found = json.loads((RESULTS / "h1.json").read_text())["verdicts"]
    table = rows(indexes.TABLES["h1-verdicts"](RESULTS))
    assert [row[0] for row in table] == [*ENGINES.values(), "Ogółem"]
    for row, key in zip(table, [*ENGINES, "overall"]):
        assert row[1] == f"*{found[key]['verdict']}*"
        assert row[2] == ", ".join(f"{cell.split()[0]} {ENGINES[cell.split()[1]]}" for cell in found[key]["failing"])


def test_every_ba_scenario_has_a_pair_chart_in_the_report():
    qa = json.loads((RESULTS / "qa.json").read_text())
    pairs = {cell["scenario"] for size in qa.values() for cell in size["cells"] if cell["config"] == "base"}
    text = "".join(path.read_text() for path in CHAPTERS.glob("*.md"))
    assert len(pairs) == 15
    for scenario in pairs:
        assert f'fig("{scenario}-ba"' in text and (RESULTS / "charts" / f"{scenario}-ba.png").is_file()


def test_censored_base_and_missing_results(tmp_path):
    assert all(table(tmp_path) is None for table in indexes.TABLES.values())
    cell = {"set": "H1-S", "scenario": "R4", "engine": "pg", "size": "L", "base_censored": True, "base_mean": None,
            "idx_mean": 1.5, "ratio": None, "direction": "faster", "plan": True, "holds": True}
    (tmp_path / "h1.json").write_text(json.dumps({"cells": [cell], "verdicts": {}}))
    assert rows(indexes.TABLES["h1-L"](tmp_path)) == [
        ["H1-S", "R4", "PostgreSQL", "> 600 000", "1 500,0", "—", "szybciej", "tak", "tak"]]
