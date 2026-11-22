import csv
import json
import math
from pathlib import Path

from bench.report.dataset import ENGINES, markdown, number

SIZES = ("S", "M", "L")
ORDER = "RCUDJ"
CENSORED = "> 600 000"
RATIO = "IDX / BASE [–]"
DIRECTIONS = {"faster": "szybciej", "slower": "wolniej", "equal": "bez zmian"}
ANSWERS = {True: "tak", False: "nie", None: "—"}
SUFFIXES = {"email": "e-mail", "phone": "telefon"}
PENDING = "weryfikacja po pomiarach L"


def read(results, name):
    path = Path(results) / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def position(scenario):
    return ORDER.index(scenario[0]), int(scenario[1:])


def milliseconds(value):
    return "—" if value is None else number(value * 1000, 1)


def ratio(value):
    return "—" if value is None else number(value, max(2, 2 - math.floor(math.log10(value))))


def mean(cell):
    if cell["state"] == "censored":
        return CENSORED
    return milliseconds(cell["mean"]) if cell["state"] == "complete" else "—"


def pairs(results, size, json_series):
    qa = read(results, "qa.json") or {}
    cells = {(cell["scenario"], cell["engine"], cell["config"]): cell for cell in qa.get(size, {}).get("cells", [])}
    scenarios = sorted({scenario for scenario, _, config in cells
                        if config == "base" and scenario.startswith("J") == json_series}, key=position)
    rows = []
    for scenario in scenarios:
        for engine, name in ENGINES.items():
            base, idx = cells.get((scenario, engine, "base")), cells.get((scenario, engine, "idx"))
            if base and idx:
                both = base["state"] == idx["state"] == "complete"
                rows.append([scenario, name, mean(base), mean(idx), ratio(idx["mean"] / base["mean"]) if both else "—"])
    return markdown(["Scenariusz", "SZBD", "BASE [ms]", "IDX [ms]", RATIO], rows,
                    ["---", "---", "--:", "--:", "--:"]) if rows else None


def widths(dashes):
    return ["-" * dash if dash > 0 else "-" * (-dash - 1) + ":" for dash in dashes]


def names(value):
    return ", ".join(f"`{name.strip()}`" for name in value.split(";") if name.strip()) or "—"


def count(value):
    return number(int(value)) if value else "—"


def access(results, size, json_series):
    path = Path(results) / "explain_summary.csv"
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8") as source:
        plans = {(row["scenario"], row["engine"], row["config"]): row for row in csv.DictReader(source)
                 if row["size"] == size and row["scenario"].startswith("J") == json_series}
    rows = []
    for scenario in sorted({scenario for scenario, _, config in plans if config == "base"}, key=position):
        rows.append([f"**{scenario}**", "", "", "", ""])
        for engine, name in ENGINES.items():
            for config in ("base", "idx"):
                row = plans.get((scenario, engine, config))
                if row:
                    rows.append([f"{name} {config.upper()}", row["access_path"].replace("; ", ", "),
                                 names(row["index"]), count(row["rows_examined"]), count(row["rows_returned"])])
    return markdown(["SZBD i konfiguracja", "Ścieżka dostępu", "Indeksy", "Przejrzane [wiersze]",
                     "Zwrócone [wiersze]"], rows, widths([17, 17, 19, -13, -12])) if rows else None


def label(name):
    key, _, suffix = name.removesuffix("__idx").partition("_")
    return key.upper() + (f" ({SUFFIXES.get(suffix, suffix)})" if suffix else "")


def build(results, json_series):
    found = read(results, "load/index_build.json") or {}
    sizes = [size for size in SIZES if size in found]
    built = {(name, engine): {size: found[size].get(engine, {}).get("indexes", {}).get(name) for size in sizes}
             for size in sizes for engine in ENGINES for name in found[size].get(engine, {}).get("indexes", {})
             if name.startswith("jx") == json_series}
    rows = []
    for name, engine in sorted(built, key=lambda key: (key[0], list(ENGINES).index(key[1]))):
        entries = built[name, engine]
        scope = next(entry["scope"] for entry in entries.values() if entry)
        cells = [label(name), ENGINES[engine], f"`{scope}`"]
        for size in sizes:
            entry = entries[size]
            cells += ["—", "—"] if entry is None else [
                number(entry["seconds"], 2), "—" if entry.get("bytes") is None else number(entry["bytes"] / 1_000_000, 1)]
        rows.append(cells)
    header = ["Indeks", "SZBD", "Obiekt"]
    for size in sizes:
        header += [f"{size}: czas [s]", f"{size}: rozmiar [MB]"]
    return markdown(header, rows, widths([13, 13, 14] + [-10] * 2 * len(sizes))) if rows else None


def base_mean(cell):
    return CENSORED if cell["base_censored"] else milliseconds(cell["base_mean"])


def evidence(results, size):
    found = read(results, "h1.json") or {}
    rows = [[cell["set"], cell["scenario"], ENGINES[cell["engine"]], base_mean(cell), milliseconds(cell["idx_mean"]),
             ratio(cell["ratio"]), DIRECTIONS.get(cell["direction"], "—"), ANSWERS[cell["plan"]], ANSWERS[cell["holds"]]]
            for cell in found.get("cells", []) if cell["size"] == size]
    return markdown(["Zbiór", "Scenariusz", "SZBD", "BASE [ms]", "IDX [ms]", RATIO, "IDX działa", "Plan IDX z indeksem",
                     "Potwierdza"], rows, widths([6, 9, 10, -9, -8, -9, 8, 9, 9])) if rows else None


def failing(cells):
    return ", ".join(f"{scenario} {ENGINES[engine]}" for scenario, engine in map(str.split, cells)) or "—"


def verdicts(results):
    found = (read(results, "h1.json") or {}).get("verdicts")
    if not found:
        return None
    rows = [[title, f"*{found[key]['verdict']}*" if found[key]["verdict"] else PENDING, failing(found[key]["failing"])]
            for key, title in {**ENGINES, "overall": "Ogółem"}.items() if key in found]
    return markdown(["SZBD", "Werdykt", "Komórki, które nie potwierdzają H1"], rows, ["---", "---", "------"])


def complete(results, size, scenario, engine, config):
    qa = read(results, "qa.json") or {}
    return next((cell for cell in qa.get(size, {}).get("cells", []) if cell["state"] == "complete"
                 and (cell["scenario"], cell["engine"], cell["config"]) == (scenario, engine, config)), None)


def mean_of(results, scenario, engine, config, size="L"):
    cell = complete(results, size, scenario, engine, config)
    return milliseconds(cell["mean"]) if cell else None


def ratio_of(results, scenario, engine, size="L"):
    base, idx = (complete(results, size, scenario, engine, config) for config in ("base", "idx"))
    return ratio(idx["mean"] / base["mean"]) if base and idx else None


def examined_of(results, scenario, engine, config, size="L"):
    path = Path(results) / "explain_summary.csv"
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8") as source:
        return next((count(row["rows_examined"]) for row in csv.DictReader(source)
                     if (row["size"], row["scenario"], row["engine"], row["config"]) == (size, scenario, engine, config)),
                    None)


VALUES = {"mean": mean_of, "ratio": ratio_of, "examined": examined_of}

TABLES = {
    "ba-core-L": lambda results: pairs(results, "L", False),
    "ba-json-L": lambda results: pairs(results, "L", True),
    "access-core-L": lambda results: access(results, "L", False),
    "access-json-L": lambda results: access(results, "L", True),
    "build-core": lambda results: build(results, False),
    "build-json": lambda results: build(results, True),
    **{f"h1-{size}": lambda results, size=size: evidence(results, size) for size in SIZES},
    "h1-verdicts": verdicts,
}
