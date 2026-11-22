import json
import re
from pathlib import Path

from bench.report import cite, document
from bench.report.dataset import ENGINES

RESULTS = Path("results")
CHAPTERS = Path("report/chapters")


def test_span_equals_qa_json():
    cell = next(cell for cell in json.loads((RESULTS / "qa.json").read_text())["L"]["cells"]
                if (cell["scenario"], cell["engine"], cell["config"]) == ("C4", "mysql", "base"))
    low, high = (float(value.replace(" ", "").replace(",", ".")) for value in
                 cite.span(RESULTS, "C4", "mysql", "base").split("–"))
    assert (low, high) == (round(cell["min"] * 1000, 1), round(cell["max"] * 1000, 1))


def test_plan_pairs_cover_every_engine_with_short_excerpts():
    text = "".join(path.read_text(encoding="utf-8") for path in sorted(CHAPTERS.glob("08-*.md")))
    pairs = re.findall(r'\{\{ plan\("(\w+)", "(\w+)", "L"', text)
    assert all(sum(engine == found for _, found in pairs) >= 2 for engine in ENGINES)
    for scenario, engine in pairs:
        listing = cite.plan(RESULTS, scenario, engine, "L", "x").split("```")[1].strip()
        parts = listing.split("\n\n")
        assert [part.splitlines()[0] for part in parts] == ["BASE:", "IDX:"]
        assert all(len(part.splitlines()) <= 8 and cite.MISSING not in part for part in parts)


def test_missing_results_render_brak_danych(tmp_path):
    text = document.resolve('{{ span("C4", "pg", "base") }}\n\n{{ plan("R4", "pg", "L", "Podpis") }}', tmp_path, "x.md")
    assert text.count(cite.MISSING) == 2 and "{#fig:plan-R4-pg .figure .listing}" in text
