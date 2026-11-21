import csv
import json
import re
from pathlib import Path

import yaml
from pptx import Presentation
from pptx.util import Inches, Pt

from bench.report.dataset import number
from bench.report.document import MISSING, ReportError, resolve

SLIDES = Path("report/slides.yaml")
TEMPLATE = Path("report/template.pptx")
CATALOGUE = Path("docs/bench/scenarios.md")
MARGIN = Inches(0.5)
GAP = Inches(0.2)
NOTE = Inches(1.0)
TITLE, CONTENT, TITLE_ONLY = 0, 1, 5
MAX_TITLE, MAX_BULLETS = 60, 6
BULLET = 24
OVERVIEW = re.compile(r"^\| ([CRUDJ]\d+) \| [CRUD] \| (.+?) \| (.+?) \| .+ \|$", re.MULTILINE)
HEADING = re.compile(r"^### ([CRUDJ]\d+) — (.+)$", re.MULTILINE)


def h1(results, engine):
    path = Path(results) / "h1.json"
    found = json.loads(path.read_text(encoding="utf-8"))["verdicts"].get(engine, {}) if path.is_file() else {}
    if not found.get("verdict"):
        return MISSING
    failing = f" ({', '.join(found['failing'])})" if found["failing"] else ""
    return found["verdict"] + failing


def plan(results, scenario, engine, config, size):
    path = Path(results) / "explain_summary.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8"))) if path.is_file() else []
    for found in dict.fromkeys((size, "S")):
        for row in rows:
            if (row["size"], row["scenario"], row["engine"], row["config"]) == (found, scenario, engine, config):
                index = f" ({row['index']})" if row["index"] else ""
                label = f" (rozmiar {found})" if found != size else ""
                return f"{row['access_path']}{index}, przejrzane wiersze: {number(int(row['rows_examined']))}{label}"
    return MISSING


MARKERS = {"h1": h1, "plan": plan}


def appendix():
    text = CATALOGUE.read_text(encoding="utf-8")
    titles = dict(HEADING.findall(text))
    rows = OVERVIEW.findall(text)
    charts = [{"title": f"{scenario} — {titles[scenario]}", "note": note, "figure": scenario}
              for scenario, note, _ in rows]
    pairs = [{"title": f"{scenario} — {titles[scenario]}: BASE i IDX", "note": note, "figure": f"{scenario}-ba"}
             for scenario, note, flags in rows if "BA" in flags.split(", ")]
    return charts + pairs


def check(items):
    for position, item in enumerate(items, start=1):
        where = f"{SLIDES}: slajd {position}"
        title = item.get("title") or ""
        if not title:
            raise ReportError(f"{where}: brak tytułu")
        if len(title) > MAX_TITLE:
            raise ReportError(f"{where}: tytuł ma {len(title)} znaków (limit {MAX_TITLE}): {title}")
        if len(item.get("bullets", [])) > MAX_BULLETS:
            raise ReportError(f"{where}: {len(item['bullets'])} punktów (limit {MAX_BULLETS}): {title}")


def place(slide, path, left, top, width, height):
    image = slide.shapes.add_picture(str(path), left, top, width=width)
    if image.height > height:
        image.width = int(image.width * height / image.height)
        image.height = height
    image.left = int(left + (width - image.width) / 2)


def text(slide, value, left, top, width, height, size):
    box = slide.shapes.add_textbox(left, top, width, height)
    box.text_frame.word_wrap = True
    box.text_frame.text = value
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(size)


def pictures(deck, slide, item, results):
    title = slide.shapes.title
    top = title.top + title.height
    width = deck.slide_width - 2 * MARGIN
    if "note" in item:
        text(slide, item["note"], MARGIN, top, width, NOTE, 18)
        top += NOTE
    height = deck.slide_height - top - MARGIN
    if "figure" in item:
        chart = Path(results) / "charts" / f"{item['figure']}.png"
        if chart.is_file():
            place(slide, chart, MARGIN, top, width, height)
        else:
            text(slide, MISSING, MARGIN, top, width, height, 28)
        return
    paths = item["images"]
    each = int((width - GAP * (len(paths) - 1)) / len(paths))
    for position, path in enumerate(paths):
        place(slide, path, MARGIN + position * (each + GAP), top, each, height)


def build(results, target):
    spec = yaml.safe_load(SLIDES.read_text(encoding="utf-8"))
    items = [{"title": spec["title"]}, *spec["slides"], *appendix()]
    check(items)
    deck = Presentation(str(TEMPLATE))
    cover = deck.slides.add_slide(deck.slide_layouts[TITLE])
    cover.shapes.title.text = spec["title"]
    cover.placeholders[1].text = spec["subtitle"]
    for position, item in enumerate(items[1:], start=2):
        if "bullets" not in item:
            slide = deck.slides.add_slide(deck.slide_layouts[TITLE_ONLY])
            slide.shapes.title.text = item["title"]
            pictures(deck, slide, item, results)
            continue
        slide = deck.slides.add_slide(deck.slide_layouts[CONTENT])
        slide.shapes.title.text = item["title"]
        body = slide.placeholders[1].text_frame
        bullets = [resolve(bullet, results, f"{SLIDES}: slajd {position}", MARKERS) for bullet in item["bullets"]]
        body.text = bullets[0]
        for bullet in bullets[1:]:
            body.add_paragraph().text = bullet
        for paragraph in body.paragraphs:
            paragraph.runs[0].font.size = Pt(BULLET)
    deck.save(str(target))
