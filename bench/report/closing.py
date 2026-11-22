import csv
import math
import re
from pathlib import Path

from bench.report.dataset import CATALOGUE, ENGINES, markdown, number
from bench.report.indexes import RATIO, milliseconds, position, ratio, read, widths

CHAPTERS = Path("report/chapters")
FOOTNOTE = re.compile(r"^\[\^[^\]]+\]:\s*(.+?)\s*$", re.MULTILINE)
CONFIGS = ("base", "idx")
CATALOGUE_START = "## Scenariusze podstawowe"
HEADING = re.compile(r"^(#{2,3}) (.+)$")
OPS = "CRUDJ"


def cells(results, size):
    found = (read(results, "qa.json") or {}).get(size, {}).get("cells", [])
    return {(cell["scenario"], cell["engine"], cell["config"]): cell for cell in found}


def summary(results):
    found = cells(results, "L")
    means = {}
    for (scenario, engine, config), cell in found.items():
        if config == "idx" and cell["state"] == "complete":
            means.setdefault(scenario, {})[engine] = cell["mean"]
    if not means:
        return None
    wins = {(engine, series): 0 for engine in ENGINES for series in (False, True)}
    logs = {engine: [] for engine in ENGINES}
    for scenario, times in means.items():
        best = min(times.values())
        wins[min(times, key=times.get), scenario.startswith("J")] += 1
        if not scenario.startswith("J"):
            for engine, value in times.items():
                logs[engine].append(math.log(value / best))
    json_engines = {engine for scenario, times in means.items() if scenario.startswith("J") for engine in times}
    rows = [[name, number(wins[engine, False]), number(wins[engine, True]) if engine in json_engines else "—",
             number(math.exp(sum(logs[engine]) / len(logs[engine])), 1) if logs[engine] else "—"]
            for engine, name in ENGINES.items()]
    return markdown(["SZBD", "Najszybszy, podstawowe [scenariusze]", "Najszybszy, JSON [scenariusze]",
                     "Średnia geometryczna krotności, podstawowe [×]"], rows, widths([10, 14, 14, -16]))


def spread(cell):
    return f"{milliseconds(cell['min'])}–{milliseconds(cell['max'])}"


def failing(results):
    verdicts = read(results, "h1.json") or {}
    named = verdicts.get("verdicts", {}).get("overall", {}).get("failing", [])
    found = cells(results, "L")
    path = Path(results) / "explain_summary.csv"
    plans = {}
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as source:
            plans = {(row["scenario"], row["engine"]): row["access_path"].replace("; ", ", ")
                     for row in csv.DictReader(source) if row["size"] == "L" and row["config"] == "idx"}
    rows = []
    for scenario, engine in sorted(map(str.split, named), key=lambda key: (position(key[0]), list(ENGINES).index(key[1]))):
        base, idx = found.get((scenario, engine, "base")), found.get((scenario, engine, "idx"))
        if base and idx:
            rows.append([scenario, ENGINES[engine], spread(base), spread(idx), ratio(idx["mean"] / base["mean"]),
                         plans.get((scenario, engine), "—")])
    return markdown(["Scenariusz", "SZBD", "BASE min–max [ms]", "IDX min–max [ms]", RATIO, "Ścieżka dostępu IDX"],
                    rows, widths([11, 12, -17, -17, -9, 21])) if rows else None


def full(results, size, config):
    found = cells(results, size)
    rows = []
    for scenario, engine, _ in sorted((key for key in found if key[2] == config),
                                      key=lambda key: (OPS.index(key[0][0]), int(key[0][1:]),
                                                       list(ENGINES).index(key[1]))):
        cell = found[scenario, engine, config]
        if cell["state"] == "complete":
            values = [milliseconds(cell[key]) for key in ("mean", "median", "min", "max")]
            rows.append([scenario, ENGINES[engine], *values, number(cell["cv"] * 100, 1)])
        else:
            rows.append([scenario, ENGINES[engine], "> 600 000" if cell["state"] == "censored" else "—",
                         "—", "—", "—", "—"])
    return markdown(["Scenariusz", "SZBD", "Średnia [ms]", "Mediana [ms]", "Min [ms]", "Max [ms]", "CV [%]"],
                    rows, widths([10, 12, -12, -12, -12, -12, -8])) if rows else None


def catalogue():
    text = CATALOGUE_START + CATALOGUE.read_text(encoding="utf-8").split(CATALOGUE_START, 1)[1]
    lines, titles = [], []
    for line in [*text.splitlines(), ""]:
        heading = HEADING.match(line)
        if heading:
            titles[len(heading.group(1)) - 2:] = [heading.group(2)]
        if lines and lines[-1].startswith("|") and not line.startswith("|"):
            title = ": ".join(titles)
            lines += ["", f": {title} {{#tab:{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}}}"]
        lines.append(line)
    return "\n".join(lines)


def sources():
    found = []
    for path in sorted(CHAPTERS.glob("*.md")):
        for entry in FOOTNOTE.findall(path.read_text(encoding="utf-8")):
            if entry not in found:
                found.append(entry)
    return "\n".join(f"{index}. {entry}" for index, entry in enumerate(found, 1))


TABLES = {
    "summary-L": summary,
    "failing-L": failing,
    **{f"full-{size}-{config}": lambda results, size=size, config=config: full(results, size, config)
       for size in ("S", "M", "L") for config in CONFIGS},
}
TEXTS = {"catalogue": catalogue, "sources": sources}
