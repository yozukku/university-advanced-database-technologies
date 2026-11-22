import argparse
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MISSING = "brak danych"
LEFTOVER = re.compile(r"\{\{\s*\w+\(|@(?:fig|tab):|\bTODO\b", re.IGNORECASE)
PLACEHOLDER = re.compile(r"\[(?:DATA|DO UZUPEŁNIENIA)[^\]]*\]")
CAPTION = re.compile(r"(Rys|Tab)\.\s([A-Z0-9]+\.\d+)\.")
REFERENCE = re.compile(r"\b(rys|tab)\.\s([A-Z0-9]+)\.(\d+)(?!\d|\.\d)(?:\sdo\s(?:rys|tab)\.\s\2\.(\d+))?",
                       re.IGNORECASE)
CAPTION_STYLES = {"ImageCaption": "Rys", "TableCaption": "Tab"}
SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml")
DPI = "100"


def attribution():
    loader = importlib.machinery.SourceFileLoader("attribution", "tools/check-attribution")
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module.ATTRIBUTION


ATTRIBUTION = attribution()


def paragraphs(root):
    for node in root.iter():
        if node.tag.endswith("}p"):
            yield "".join(child.text or "" for child in node.iter() if child.tag.endswith("}t"))


def parts(archive):
    for name in archive.namelist():
        if name.endswith(".xml"):
            root = ElementTree.fromstring(archive.read(name))
            texts = (node.text or "" for node in root.iter()) if name.startswith("docProps/") else paragraphs(root)
            yield name, root, [text for text in texts if text.strip()]


def text_problems(label, text):
    found = []
    if MISSING in text.lower():
        found.append("„brak danych”")
    if LEFTOVER.search(text):
        found.append("nierozwiązany znacznik")
    if ATTRIBUTION.search(text):
        found.append("wpis o autorstwie")
    return [f"{label}: {kind}: {text.strip()[:80]}" for kind in found]


def style(node):
    found = node.find(f"{W}pPr/{W}pStyle")
    return found.get(f"{W}val") if found is not None else None


def caption(node, kind):
    text = "".join(paragraphs(node))
    match = CAPTION.match(text) if node.tag == f"{W}p" and CAPTION_STYLES.get(style(node)) == kind else None
    return match.group(2) if match and match.group(1) == kind else None


def numbering(body):
    nodes = list(body)
    problems = []
    for position, node in enumerate(nodes):
        if node.tag == f"{W}tbl" and not (position and caption(nodes[position - 1], "Tab")):
            problems.append(f"tabela bez numeru: {''.join(paragraphs(node))[:80]}")
        if node.tag == f"{W}p" and node.find(f".//{W}drawing") is not None and not (
                position + 1 < len(nodes) and caption(nodes[position + 1], "Rys")):
            problems.append(f"rysunek bez numeru po: {''.join(paragraphs(nodes[position - 1]))[:80]}")
    return problems


def references(texts, captions):
    cited = set()
    for kind, chapter, first, last in REFERENCE.findall("\n".join(texts)):
        cited.update((kind.capitalize(), f"{chapter}.{number}") for number in range(int(first), int(last or first) + 1))
    return [f"{kind}. {number} nie ma odwołania w tekście" for kind, number in captions if (kind, number) not in cited]


def document_problems(path):
    problems, prose, captions = [], [], []
    with zipfile.ZipFile(path) as archive:
        for name, root, texts in parts(archive):
            problems += [problem for text in texts for problem in text_problems(f"{path} ({name})", text)]
            if name == "word/document.xml":
                body = root.find(f"{W}body")
                problems += [f"{path}: {problem}" for problem in numbering(body)]
                for node in root.iter(f"{W}p"):
                    kind = CAPTION_STYLES.get(style(node))
                    number = caption(node, kind) if kind else None
                    if number:
                        captions.append((kind, number))
                    elif not (style(node) or "").startswith("TOC"):
                        prose.append("".join(paragraphs(node)))
            elif name == "word/footnotes.xml":
                prose += texts
    return problems + [f"{path}: {problem}" for problem in references(prose, captions)]


def deck_problems(path):
    problems = []
    with zipfile.ZipFile(path) as archive:
        for name, _, texts in parts(archive):
            slide = SLIDE.fullmatch(name)
            label = f"{path} slajd {slide.group(1)}" if slide else f"{path} ({name})"
            problems += [problem for text in texts for problem in text_problems(label, text)]
    return problems


def placeholders(path):
    with zipfile.ZipFile(path) as archive:
        return [match for _, _, texts in parts(archive) for text in texts for match in PLACEHOLDER.findall(text)]


def clean_clone(results):
    path = results / "clean-clone.json"
    if not path.is_file():
        return [f"{path}: brak pliku, uruchom dowód na czystym klonie"]
    proof = json.loads(path.read_text(encoding="utf-8"))
    sha = str(proof.get("sha") or "")
    ancestor = subprocess.run(["git", "-c", "safe.directory=*", "merge-base", "--is-ancestor", sha, "HEAD"],
                              capture_output=True) if sha else None
    problems = [] if ancestor and ancestor.returncode == 0 else [f"{path}: commit {sha or '—'} nie jest przodkiem HEAD"]
    if proof.get("exit") != 0:
        problems.append(f"{path}: uruchomienie na czystym klonie zakończone kodem {proof.get('exit')}")
    return problems


def render(out):
    pages = out / "pages"
    shutil.rmtree(pages, ignore_errors=True)
    pages.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as work:
        profile, converted = Path(work) / "profile", Path(work) / "pdf"
        subprocess.run(["soffice", "--headless", f"-env:UserInstallation={profile.as_uri()}", "--convert-to", "pdf",
                        "--outdir", str(converted), str(out / "prezentacja.pptx")], check=True, capture_output=True)
        for pdf, name in ((out / "sprawozdanie.pdf", "sprawozdanie"), (converted / "prezentacja.pdf", "prezentacja")):
            subprocess.run(["pdftoppm", "-r", DPI, "-png", str(pdf), str(pages / name)], check=True)
    return pages


def main():
    parser = argparse.ArgumentParser(description="Sprawdza sprawozdanie i prezentację i zapisuje ich strony jako PNG")
    parser.add_argument("--results", type=Path, default=Path(os.environ.get("RESULTS_DIR", "results")))
    parser.add_argument("--out", type=Path, default=Path("out"))
    arguments = parser.parse_args()
    files = {name: arguments.out / name for name in ("sprawozdanie.docx", "sprawozdanie.pdf", "prezentacja.pptx")}
    missing = [path for path in files.values() if not path.is_file()]
    problems = clean_clone(arguments.results) + [f"{path}: brak pliku, uruchom make report" for path in missing]
    if not missing:
        problems +=document_problems(files["sprawozdanie.docx"]) + deck_problems(files["prezentacja.pptx"])
        for found in placeholders(files["sprawozdanie.docx"]):
            print(f"do uzupełnienia przez autorów: {found}")
        print(render(arguments.out))
    for problem in problems:
        print(problem, file=sys.stderr)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
