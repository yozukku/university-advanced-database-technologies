import json
import re
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from bench.report import document, slides
from bench.report.document import MISSING, ReportError

FIXTURE = Path(__file__).with_name("results-S")


def parse(markdown, label="3"):
    parsed = json.loads(document.pandoc(["-f", "markdown", "-t", "json"], markdown))
    targets = {}
    document.number(parsed["blocks"], label, targets, "test.md")
    document.link(parsed["blocks"], targets)
    return parsed["blocks"]


def strings(blocks):
    return [node["c"] for node in document.nodes(blocks) if node["t"] == "Str"]


def docx_text(path):
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    paragraphs = []
    for paragraph in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        style = re.search(r'<w:pStyle w:val="([^"]+)"', paragraph)
        paragraphs.append((style.group(1) if style else "", "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", paragraph))))
    return paragraphs, media


def opens(path, tmp_path):
    subprocess.run(["soffice", "--headless", f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}",
                    "--convert-to", "pdf", "--outdir", str(tmp_path / "opened"), str(path)],
                   check=True, capture_output=True, timeout=300)
    return (tmp_path / "opened" / f"{path.stem}.pdf").read_bytes().startswith(b"%PDF")


def test_markers_render_missing_inputs_as_brak_danych(tmp_path):
    text = document.resolve('{{ fig("R1", "Podpis") }}\n\n{{ table("R-S", "Tabela") }}\n', tmp_path, "x.md")
    assert text.count(MISSING) == 2
    assert "{#fig:R1 .figure}" in text and "{#tab:R-S}" in text


def test_markers_include_existing_inputs():
    text = document.resolve('{{ fig("R1", "Podpis") }}\n{{ table("R", "Tabela") }}', FIXTURE, "x.md")
    assert f"![](<{FIXTURE / 'charts' / 'R1.png'}>)" in text
    assert "| R1 | 1,2 |" in text and MISSING not in text


@pytest.mark.parametrize("marker", ['{{ chart("R1", "x") }}', '{{ fig(R1, "x") }}', '{{ fig("R1") }}', '{{ fig "R1" }}'])
def test_unresolved_markers_fail(marker, tmp_path):
    with pytest.raises(ReportError, match="nierozwiązany znacznik"):
        document.resolve(f"# Rozdział\n\n{marker}\n", tmp_path, "x.md")


def test_numbering_of_sections_captions_and_references(tmp_path):
    markdown = document.resolve("\n".join([
        "# Wyniki", "", "Na @fig:R1 i @Tab:R widać [@fig:R1; @tab:inna].", "", "## Odczyt", "", "### R1", "",
        '{{ fig("R1", "Wykres") }}', "", '{{ table("R", "Tabela") }}', "", "| a |", "|---|", "| 1 |", "",
        ": Inna {#tab:inna}", "", "## Zapis {-}", "", "## Usuwanie"]), FIXTURE, "x.md")
    found = strings(parse(markdown))
    assert {"3.", "3.1.", "3.1.1.", "3.2.", "Rys.\u00a03.1.", "Tab.\u00a03.1.", "Tab.\u00a03.2."} <= set(found)
    assert {"rys.\u00a03.1", "Tab.\u00a03.1", "rys.\u00a03.1, tab.\u00a03.2"} <= set(found)
    assert "3.3." not in found and not [text for text in found if text.startswith("{#")]


def test_unknown_reference_fails():
    with pytest.raises(ReportError, match="nieznane odwołanie @fig:brak"):
        parse("# Wyniki\n\nZob. @fig:brak.\n")


def test_chapter_needs_one_top_heading():
    with pytest.raises(ReportError, match="więcej niż jeden"):
        parse("# Jeden\n\n# Dwa\n")


def test_report_builds_from_s_only_results(tmp_path):
    document.build(FIXTURE, tmp_path)
    paragraphs, media = docx_text(tmp_path / "sprawozdanie.docx")
    texts = [text for _, text in paragraphs]
    toc = [text for style, text in paragraphs if style.startswith("TOC") or style.startswith("Contents")]
    assert any(text.startswith("Spis treści") for text in texts)
    assert any(text.startswith("3. Zbiór danych i modele danych") for text in toc)
    assert any(text.startswith("7. Wyniki CRUD") for text in toc)
    assert any(text.startswith("13. Harmonogram i podział prac") for text in toc)
    assert any(text.startswith("Rys.\u00a07.1. Czas odczytu R1") for text in texts)
    assert any(text.startswith("Tab.\u00a07.2. Średnie czasy scenariuszy odczytu") for text in texts)
    assert any(text.startswith("Rys.\u00a03.1. Diagram ERD: przegląd 13 tabel") for text in texts)
    assert any(text.startswith("Rys.\u00a03.10. Model grafowy w Neo4j") for text in texts)
    assert any(text.startswith("Tab.\u00a03.1. Liczba rekordów") for text in texts)
    assert "500\u00a0000" in texts and "`" not in "".join(texts)
    assert "R2" in texts and len(media) == 15
    assert texts.count(MISSING) == 7
    assert not [text for text in texts if "{{" in text or "@fig:" in text or "@tab:" in text]
    assert (tmp_path / "sprawozdanie.pdf").read_bytes().startswith(b"%PDF")
    assert opens(tmp_path / "sprawozdanie.docx", tmp_path)


def test_report_without_results_renders_brak_danych(tmp_path):
    document.build(tmp_path / "missing", tmp_path)
    paragraphs, _ = docx_text(tmp_path / "sprawozdanie.docx")
    assert [text for _, text in paragraphs].count(MISSING) == 13


def test_presentation_opens(tmp_path):
    target = tmp_path / "prezentacja.pptx"
    slides.build(FIXTURE, target)
    deck = Presentation(str(target))
    spec = yaml.safe_load(slides.SLIDES.read_text(encoding="utf-8"))
    assert len(deck.slides) == 1 + len(spec["slides"]) + 47
    assert all(slide.shapes.title.text for slide in deck.slides)
    assert any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for slide in deck.slides for shape in slide.shapes)
    assert opens(target, tmp_path)


@pytest.mark.parametrize("item", [{"title": "T" * 61, "bullets": ["a"]}, {"title": "T", "bullets": ["a"] * 7}])
def test_presentation_limits_fail(item, tmp_path, monkeypatch):
    spec = yaml.safe_load(slides.SLIDES.read_text(encoding="utf-8"))
    source = tmp_path / "slides.yaml"
    source.write_text(yaml.safe_dump({**spec, "slides": [*spec["slides"], item]}, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(slides, "SLIDES", source)
    with pytest.raises(ReportError, match="limit"):
        slides.build(FIXTURE, tmp_path / "prezentacja.pptx")
