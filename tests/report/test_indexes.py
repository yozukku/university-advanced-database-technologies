import json
from pathlib import Path

from bench.report import crud, document, indexes
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


def test_inline_values_equal_the_l_tables_and_render_brak_danych_without_results(tmp_path):
    pairs = {row[0] + " " + row[1]: row for row in rows(indexes.TABLES["ba-json-L"](RESULTS))}
    assert document.resolve('{{ mean("J2", "pg", "base") }} {{ ratio("J2", "pg") }}', RESULTS, "x") == \
        f'{pairs["J2 PostgreSQL"][2]} {pairs["J2 PostgreSQL"][4]}'
    access = {(row[0], row[1], row[2]): row for row in rows(indexes.TABLES["access-core-L"](RESULTS))}
    assert document.resolve('{{ examined("R5", "pg", "idx") }}', RESULTS, "x") == access["R5", "PostgreSQL", "IDX"][5]
    assert document.resolve('{{ ratio("J2", "pg", "M") }}', tmp_path, "x") == document.MISSING


def test_clean_clone_table_sums_the_clone_steps(tmp_path):
    steps = [{"size": "XS", "step": "load", "engine": engine, "state_id": "a", "seconds": 2.0, "exit": 0}
             for engine in ("pg", "mysql")] + [{"size": None, "step": "report", "engine": None, "state_id": None,
                                                "seconds": 3.5, "exit": 0}]
    (tmp_path / "clean-clone.json").write_text(json.dumps(
        {"sha": "0123456789abcdef", "date": "2026-11-22", "sizes": "XS", "exit": 0, "steps": steps}))
    assert rows(crud.TABLES["clean-clone"](tmp_path)) == [
        ["Commit", "`0123456789ab`"], ["Data", "2026-11-22"], ["Polecenie", "`make full SIZES=XS`"],
        ["Kod wyjścia", "0"], ["`load` [s]", "4,0"], ["`report` [s]", "3,5"], ["**Razem [s]**", "**7,5**"]]
