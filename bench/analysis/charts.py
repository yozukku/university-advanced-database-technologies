import argparse
import json
import re
from math import floor, log10
from pathlib import Path
from statistics import mean

import matplotlib
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from bench.report.dataset import ENGINES, SIZES

COLOURS = {"pg": "#2a78d6", "mysql": "#eb6834", "mongo": "#1baf7a", "neo4j": "#eda100"}
CELL = ("engine", "size", "config", "scenario")
RUNS = 3
LOG_RATIO = 50
LOG_NOTE = "skala logarytmiczna"
UNIT = re.compile(r"\[(ms|s|×)\]")
THIN = " "
INK = "#52514e"
TEXT = "#1f1f1e"
OPS = "CRUD"
RAMP = LinearSegmentedColormap.from_list("ramp", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])

matplotlib.rcParams.update({
    "font.size": 8, "axes.edgecolor": "#8a8984", "axes.labelcolor": TEXT, "xtick.color": INK,
    "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "axes.grid.axis": "y", "axes.axisbelow": True, "grid.color": "#e4e3df", "grid.linewidth": 0.6,
    "legend.frameon": False, "savefig.dpi": 300,
})


def polish(value):
    return f"{value:,.6f}".rstrip("0").rstrip(".").replace(",", THIN).replace(".", ",")


def complete(results):
    path = Path(results) / "runs.jsonl"
    current, groups = {}, {}
    for raw in path.read_text().splitlines() if path.is_file() else ():
        if raw.strip():
            line = json.loads(raw)
            cell = tuple(line[field] for field in CELL)
            current[cell] = line["qhash"], line["state_id"]
            groups.setdefault((cell, current[cell]), []).append(line)
    found = {}
    for cell, version in current.items():
        lines = groups[cell, version]
        if len(lines) == RUNS and all(line["status"] == "ok" for line in lines):
            found[cell] = [line["nanoseconds"] / 1e6 for line in lines]
    return found


def series(cells, scenario, config):
    return {(engine, size): times for (engine, size, kind, name), times in cells.items()
            if kind == config and name == scenario}


def present(found):
    return ([engine for engine in ENGINES if any(key[0] == engine for key in found)],
            [size for size in SIZES if any(key[1] == size for key in found)])


def unit(found):
    return (1000, "s") if max(max(times) for times in found.values()) >= 1000 else (1, "ms")


def value_axis(axes, name, log, lowest, top=None):
    axes.set_ylabel(f"Średni czas [{name}]" + (f", {LOG_NOTE}" if log else ""))
    if log:
        axes.set_yscale("log")
        axes.set_ylim(10 ** floor(log10(lowest / 2)), top)
        axes.yaxis.set_major_locator(LogLocator(subs=(1, 2, 5)))
        axes.yaxis.set_minor_formatter(NullFormatter())
    axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: polish(value)))


def scenario_chart(cells, scenario):
    found = series(cells, scenario, "idx")
    engines, sizes = present(found)
    divisor, name = unit(found)
    means = [mean(times) for times in found.values()]
    log = max(means) / min(means) >= LOG_RATIO
    figure = Figure(figsize=(6.3, 3.2), layout="constrained")
    axes = figure.add_subplot()
    width = 0.8 / len(engines)
    for slot, engine in enumerate(engines):
        bars = [(index, found[engine, size]) for index, size in enumerate(sizes) if (engine, size) in found]
        heights = [mean(times) / divisor for _, times in bars]
        whiskers = [[height - min(times) / divisor for height, (_, times) in zip(heights, bars)],
                    [max(times) / divisor - height for height, (_, times) in zip(heights, bars)]]
        axes.bar([index + (slot - (len(engines) - 1) / 2) * width for index, _ in bars], heights, width,
                 color=COLOURS[engine], edgecolor="white", linewidth=1, label=ENGINES[engine], yerr=whiskers,
                 capsize=2, error_kw={"elinewidth": 0.7, "capthick": 0.7, "ecolor": INK})
    value_axis(axes, name, log, min(min(times) for times in found.values()) / divisor)
    axes.set_xticks(range(len(sizes)), sizes)
    axes.set_xlabel("Rozmiar zbioru danych")
    axes.legend(ncols=len(engines), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    caption = (f"{scenario}: średni czas trzech przebiegów w konfiguracji IDX według SZBD i rozmiaru danych, "
               f"wąsy: min–max" + (f"; {LOG_NOTE}" if log else "") + ".")
    return figure, caption


def pair_chart(cells, scenario):
    found = {(engine, size, config): times for config in ("base", "idx")
             for (engine, size), times in series(cells, scenario, config).items()}
    engines, sizes = present(found)
    divisor, name = unit(found)
    heights = {key: mean(times) / divisor for key, times in found.items()}
    figure = Figure(figsize=(6.3, 3.2), layout="constrained")
    panels = figure.subplots(1, len(engines), sharey=True, squeeze=False)[0]
    for axes, engine in zip(panels, engines):
        axes.set_title(ENGINES[engine])
        for index, size in enumerate(sizes):
            base, idx = heights.get((engine, size, "base")), heights.get((engine, size, "idx"))
            if base:
                axes.bar(index - 0.2, base, 0.4, color="white", edgecolor=COLOURS[engine], hatch="////", linewidth=0.8)
            if idx:
                axes.bar(index + 0.2, idx, 0.4, color=COLOURS[engine], edgecolor="white", linewidth=1)
            if base and idx:
                axes.text(index, max(base, idx) * 1.25, "×" + polish(float(f"{idx / base:.2g}")), ha="center",
                          color=TEXT)
        axes.set_xticks(range(len(sizes)), sizes)
    value_axis(panels[0], name, True, min(heights.values()), max(heights.values()) * 4)
    figure.legend(handles=[Patch(facecolor="white", edgecolor=INK, hatch="////", label="BASE"),
                           Patch(facecolor=INK, label="IDX")], ncols=2, loc="outside upper center")
    figure.supxlabel("Rozmiar zbioru danych", fontsize=8)
    caption = (f"{scenario}: średni czas trzech przebiegów w konfiguracjach BASE i IDX, nad parą stosunek "
               f"IDX / BASE; {LOG_NOTE}.")
    return figure, caption


def heat_map(cells, size):
    found = {(scenario, engine): mean(times) for (engine, kind_size, config, scenario), times in cells.items()
             if kind_size == size and config == "idx" and scenario[0] in OPS}
    scenarios = sorted({scenario for scenario, _ in found}, key=lambda name: (OPS.index(name[0]), int(name[1:])))
    engines = [engine for engine in ENGINES if any(key[1] == engine for key in found)]
    fastest = {scenario: min(value for key, value in found.items() if key[0] == scenario) for scenario in scenarios}
    ratios = [[found[scenario, engine] / fastest[scenario] if (scenario, engine) in found else float("nan")
               for engine in engines] for scenario in scenarios]
    top = max(max(value for value in row if value == value) for row in ratios)
    norm = LogNorm(1, max(top, 2))
    figure = Figure(figsize=(5.2, 0.22 * len(scenarios) + 1.1), layout="constrained")
    axes = figure.add_subplot()
    image = axes.imshow(ratios, cmap=RAMP, norm=norm, aspect="auto")
    for row, values in enumerate(ratios):
        for column, value in enumerate(values):
            if value == value:
                axes.text(column, row, "×" + polish(float(f"{value:.2g}")), ha="center", va="center", fontsize=7,
                          color="white" if norm(value) > 0.5 else TEXT)
    for row in range(1, len(scenarios)):
        if scenarios[row][0] != scenarios[row - 1][0]:
            axes.axhline(row - 0.5, color="white", linewidth=2)
    axes.set_xticks(range(len(engines)), [ENGINES[engine] for engine in engines])
    axes.set_yticks(range(len(scenarios)), scenarios)
    axes.xaxis.tick_top()
    axes.tick_params(length=0)
    axes.grid(False)
    for spine in axes.spines.values():
        spine.set_visible(False)
    bar = figure.colorbar(image, ax=axes, shrink=0.6)
    bar.set_label("Czas względem najszybszego SZBD [×], skala logarytmiczna")
    bar.ax.yaxis.set_major_locator(LogLocator(subs=(1, 2, 5)))
    bar.ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: polish(value)))
    bar.ax.yaxis.set_minor_formatter(NullFormatter())
    caption = (f"Średni czas scenariuszy CRUD w konfiguracji IDX przy rozmiarze {size} jako krotność czasu "
               f"najszybszego SZBD w danym scenariuszu; {LOG_NOTE}.")
    return figure, caption


def save(figure, path):
    labels = [axes.get_ylabel() for axes in figure.axes if axes.get_ylabel()]
    if not labels or not all(UNIT.search(label) for label in labels):
        raise ValueError(f"{path.name}: oś wartości bez jednostki [ms] albo [s]")
    figure.savefig(path)


def write(results):
    cells = complete(results)
    target = Path(results) / "charts"
    target.mkdir(parents=True, exist_ok=True)
    charts = {}
    for scenario in sorted({cell[3] for cell in cells}):
        if series(cells, scenario, "idx"):
            charts[scenario] = scenario_chart(cells, scenario)
        if series(cells, scenario, "base"):
            charts[f"{scenario}-ba"] = pair_chart(cells, scenario)
    for size in SIZES:
        if any(cell[1] == size and cell[2] == "idx" and cell[3][0] in OPS for cell in cells):
            charts[f"heatmap-{size}"] = heat_map(cells, size)
    for name, (figure, _) in charts.items():
        save(figure, target / f"{name}.png")
    captions = {name: caption for name, (_, caption) in charts.items()}
    (target / "captions.json").write_text(json.dumps(captions, ensure_ascii=False, indent=2) + "\n")
    return captions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results")
    args = parser.parse_args()
    captions = write(args.results)
    print(f"{len(captions)} wykresów w {Path(args.results) / 'charts'}")


if __name__ == "__main__":
    main()
