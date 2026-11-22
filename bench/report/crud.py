import json
from math import log10
from pathlib import Path

from bench.analysis.steps import durations
from bench.report.dataset import ENGINES, SIZES, loads, markdown, number

OPS = ("C", "R", "U", "D")
MODELS = {"pg": "relacyjny", "mysql": "relacyjny", "mongo": "dokumentowy", "neo4j": "grafowy"}
MODEL_CASES = {"R1": "szczegóły zamówienia", "D2": "usunięcie zamówień z zależnymi", "R8": "zasięg po połączeniach przesyłek"}
STEPS = ("data", "validate", "load", "verify", "snapshots", "bench", "explain", "qa", "charts", "h1", "report")


def order(scenario):
    return OPS.index(scenario[0]), int(scenario[1:])


def means(results):
    path = Path(results) / "qa.json"
    found = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {size: {(cell["scenario"], cell["engine"]): cell["mean"] * 1000 for cell in found[size]["cells"]
                   if cell["config"] == "idx" and cell["state"] == "complete" and cell["scenario"][0] in OPS}
            for size in SIZES if size in found}


def milliseconds(found, key):
    return number(found[key], 1) if key in found else "—"


def operation(results, op):
    found = means(results)
    names = sorted({scenario for cells in found.values() for scenario, _ in cells if scenario[0] == op}, key=order)
    rows = [[scenario, size, *(milliseconds(cells, (scenario, engine)) for engine in ENGINES)]
            for scenario in names for size, cells in found.items()]
    header = ["Scenariusz", "Rozmiar", *(f"{name} [ms]" for name in ENGINES.values())]
    return markdown(header, rows, ["---", "---"] + ["--:"] * len(ENGINES)) if rows else None


def slope(points):
    xs, ys = zip(*((log10(records), log10(value)) for records, value in points))
    x0, y0 = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((x - x0) * (y - y0) for x, y in zip(xs, ys)) / sum((x - x0) ** 2 for x in xs)


def scaling(results):
    found = means(results)
    records = {size: sum(table["rows"] for table in data["canonical"]["tables"].values())
               for size, data in loads(results).items() if size in found}
    if len(records) < 2:
        return None
    rows = []
    for scenario in sorted({scenario for size in records for scenario, _ in found[size]}, key=order):
        cells = []
        for engine in ENGINES:
            points = [(records[size], found[size][scenario, engine]) for size in records
                      if (scenario, engine) in found[size]]
            cells.append(number(round(slope(points), 2) + 0.0, 2).replace("-", "−") if len(points) >= 2 else "—")
        rows.append([scenario, *cells])
    return markdown(["Scenariusz", *(f"{name} [–]" for name in ENGINES.values())], rows)


def models(results):
    found = means(results).get("L")
    if not found:
        return None
    rows = [[scenario, text, *(milliseconds(found, (scenario, engine)) for engine in ENGINES)]
            for scenario, text in MODEL_CASES.items()]
    header = ["Scenariusz", "Operacja", *(f"{name}, {MODELS[engine]} [ms]" for engine, name in ENGINES.items())]
    return markdown(header, rows, ["---", "---"] + ["--:"] * len(ENGINES))


def steps(results):
    path = Path(results) / "full-run.jsonl"
    if not path.is_file():
        return None
    totals = {}
    for (size, step, _), seconds in durations([json.loads(raw) for raw in path.read_text().splitlines()
                                                if raw.strip()]).items():
        totals[size, step] = totals.get((size, step), 0) + seconds
    sizes = [size for size in SIZES if any(key[0] == size for key in totals)]
    rows = []
    for step in STEPS:
        cells = [totals.get((size, step)) for size in [*sizes, None]]
        if any(value is not None for value in cells):
            rows.append([f"`{step}`", *("—" if value is None else number(value, 1) for value in cells[:-1]),
                         number(sum(value or 0 for value in cells), 1)])
    sums = [sum(value for key, value in totals.items() if key[0] == size) for size in sizes]
    rows.append(["**Razem**", *(f"**{number(value, 1)}**" for value in sums),
                 f"**{number(sum(totals.values()), 1)}**"])
    return markdown(["Krok", *(f"{size} [s]" for size in sizes), "Razem [s]"], rows)


TABLES = {"scaling": scaling, "models": models, "steps": steps}
