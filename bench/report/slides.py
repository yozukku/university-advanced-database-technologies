from pathlib import Path

import yaml
from pptx import Presentation
from pptx.util import Inches, Pt

from bench.report.document import MISSING

SLIDES = Path("report/slides.yaml")
TEMPLATE = Path("report/template.pptx")
MARGIN = Inches(0.5)
TITLE, CONTENT, TITLE_ONLY = 0, 1, 5


def picture(deck, slide, chart):
    title = slide.shapes.title
    top = title.top + title.height
    width = deck.slide_width - 2 * MARGIN
    height = deck.slide_height - top - MARGIN
    if not chart.is_file():
        box = slide.shapes.add_textbox(MARGIN, top, width, height)
        box.text_frame.text = MISSING
        box.text_frame.paragraphs[0].runs[0].font.size = Pt(28)
        return
    image = slide.shapes.add_picture(str(chart), MARGIN, top, width=width)
    if image.height > height:
        image.width = int(image.width * height / image.height)
        image.height = height
    image.left = int((deck.slide_width - image.width) / 2)


def build(results, target):
    spec = yaml.safe_load(SLIDES.read_text(encoding="utf-8"))
    deck = Presentation(str(TEMPLATE))
    cover = deck.slides.add_slide(deck.slide_layouts[TITLE])
    cover.shapes.title.text = spec["title"]
    cover.placeholders[1].text = spec["subtitle"]
    for item in spec["slides"]:
        if "figure" in item:
            slide = deck.slides.add_slide(deck.slide_layouts[TITLE_ONLY])
            slide.shapes.title.text = item["title"]
            picture(deck, slide, Path(results) / "charts" / f"{item['figure']}.png")
            continue
        slide = deck.slides.add_slide(deck.slide_layouts[CONTENT])
        slide.shapes.title.text = item["title"]
        body = slide.placeholders[1].text_frame
        body.text = item["bullets"][0]
        for bullet in item["bullets"][1:]:
            body.add_paragraph().text = bullet
    deck.save(str(target))
