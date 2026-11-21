import ast
import json
import re
import subprocess
from pathlib import Path

from bench.report import dataset

CHAPTERS = Path("report/chapters")
METADATA = Path("report/metadata.yaml")
REFERENCE = Path("report/reference.docx")
OFFICE = Path(__file__).with_name("office.py")
MISSING = "brak danych"
EMPTY_TABLE = f"| {MISSING} |\n|---|"
MARKER = re.compile(r"\{\{\s*(\w+)\((.*?)\)\s*\}\}")
LEFTOVER = re.compile(r"\{\{.*?\}\}", re.DOTALL)
CAPTION_ID = re.compile(r"\{#((?:fig|tab):[^\s{}]+)\}")
CAPTIONS = {"Figure": ("fig", "Rys."), "Table": ("tab", "Tab.")}
REFERENCES = {"fig": "rys.", "tab": "tab."}


class ReportError(Exception):
    pass


def figure(results, name, caption):
    chart = Path(results) / "charts" / f"{name}.png"
    body = f"![](<{chart}>)" if chart.is_file() else MISSING
    return f"::: {{#fig:{name} .figure}}\n{body}\n\n{caption}\n:::"


def captioned(body, name, caption):
    return f"{body or EMPTY_TABLE}\n\n: {caption} {{#tab:{name}}}"


def table(results, name, caption):
    fragment = Path(results) / "tables" / f"{name}.md"
    return captioned(fragment.read_text(encoding="utf-8").strip() if fragment.is_file() else None, name, caption)


def data(results, name, caption):
    return captioned(dataset.TABLES[name](results), name, caption)


def sample(results, name, caption):
    return f"::: {{#fig:{name} .figure .listing}}\n```\n{dataset.sample(name)}\n```\n\n{caption}\n:::"


MARKERS = {"fig": figure, "table": table, "dataset": data, "sample": sample}


def resolve(text, results, source, markers=MARKERS):
    def replace(match):
        name, arguments = match.groups()
        line = text.count("\n", 0, match.start()) + 1
        try:
            return markers[name](results, *ast.literal_eval(f"({arguments},)"))
        except (KeyError, SyntaxError, TypeError, ValueError) as error:
            raise ReportError(f"{source}:{line}: nierozwiązany znacznik {match.group()}") from error

    resolved = MARKER.sub(replace, text)
    leftover = LEFTOVER.search(resolved)
    if leftover:
        raise ReportError(f"{source}: nierozwiązany znacznik {leftover.group()}")
    return resolved


def nodes(value):
    if isinstance(value, dict):
        if "t" in value:
            yield value
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from nodes(item)


def text(value):
    return {"t": "Str", "c": value}


def as_figure(node):
    (identifier, classes, attributes), content = node["c"]
    node["t"] = "Figure"
    node["c"] = [[identifier, [name for name in classes if name != "figure"], attributes],
                 [None, [{"t": "Plain", "c": content[-1]["c"]}]], content[:-1]]


def as_listing(node):
    attributes, (_, caption), content = node["c"]
    style = ["", [], [["custom-style", "Image Caption"]]]
    node["t"] = "Div"
    node["c"] = [attributes, [*content, {"t": "Div", "c": [style, [{"t": "Para", "c": caption[0]["c"]}]]}]]


def number_header(node, label, sections, source):
    level, attributes, inlines = node["c"]
    if level > 3 or "unnumbered" in attributes[1]:
        return
    if level == 1:
        if sections[0] is not None:
            raise ReportError(f"{source}: rozdział ma więcej niż jeden nagłówek pierwszego poziomu")
        sections[:] = [0, 0, 0]
    elif sections[0] is None:
        raise ReportError(f"{source}: rozdział musi zaczynać się nagłówkiem pierwszego poziomu")
    else:
        sections[level - 1] += 1
        sections[level:] = [0] * (3 - level)
    inlines[:0] = [text(".".join([label, *map(str, sections[1:level])]) + "."), {"t": "Space"}]
    if attributes[0]:
        attributes[0] = f"{label}-{attributes[0]}"


def number_caption(node, label, counts, targets, source):
    kind, word = CAPTIONS[node["t"]]
    attributes, (_, blocks) = node["c"][:2]
    if not blocks:
        return
    inlines = blocks[0]["c"]
    found = inlines and inlines[-1]["t"] == "Str" and CAPTION_ID.fullmatch(inlines[-1]["c"])
    if found:
        attributes[0] = found.group(1)
        del inlines[-1]
        while inlines and inlines[-1]["t"] == "Space":
            del inlines[-1]
    counts[kind] += 1
    number = f"{label}.{counts[kind]}"
    inlines[:0] = [text(f"{word}\u00a0{number}."), {"t": "Space"}]
    if attributes[0]:
        if attributes[0] in targets:
            raise ReportError(f"{source}: powtórzony identyfikator {attributes[0]}")
        targets[attributes[0]] = number


def number(blocks, label, targets, source):
    sections = [None, 0, 0]
    counts = {"fig": 0, "tab": 0}
    for node in nodes(blocks):
        if node["t"] == "Div" and "figure" in node["c"][0][1]:
            as_figure(node)
        if node["t"] == "Header":
            number_header(node, label, sections, source)
        elif node["t"] in CAPTIONS:
            number_caption(node, label, counts, targets, source)
            if "listing" in node["c"][0][1]:
                as_listing(node)


def link(blocks, targets):
    for node in nodes(blocks):
        if node["t"] != "Cite":
            continue
        keys = [citation["citationId"] for citation in node["c"][0]]
        if keys[0].partition(":")[0].lower() not in REFERENCES:
            continue
        labels = []
        for key in keys:
            kind, _, name = key.partition(":")
            target = targets.get(f"{kind.lower()}:{name}")
            if kind.lower() not in REFERENCES or target is None:
                raise ReportError(f"nieznane odwołanie @{key}")
            word = REFERENCES[kind.lower()]
            labels.append(f"{word.capitalize() if kind[0].isupper() else word}\u00a0{target}")
        node["t"], node["c"] = "Str", ", ".join(labels)


def pandoc(arguments, source):
    result = subprocess.run(["pandoc", "--fail-if-warnings", *arguments], input=source, capture_output=True,
                            text=True, encoding="utf-8")
    if result.returncode:
        raise ReportError(f"pandoc: {result.stderr.strip()}")
    return result.stdout


def chapter_label(path):
    return path.name.split("-", 1)[0].lstrip("0")


def build(results, out):
    work = out / "report-build"
    work.mkdir(parents=True, exist_ok=True)
    targets = {}
    document = None
    for path in sorted(CHAPTERS.glob("*.md")):
        resolved = resolve(path.read_text(encoding="utf-8"), results, path)
        (work / path.name).write_text(resolved, encoding="utf-8")
        parsed = json.loads(pandoc(["-f", "markdown", "-t", "json"], resolved))
        number(parsed["blocks"], chapter_label(path), targets, path)
        if document is None:
            document = parsed
        else:
            document["blocks"] += parsed["blocks"]
    link(document["blocks"], targets)
    draft = work / "sprawozdanie.docx"
    pandoc(["-f", "json", "-t", "docx", "--toc", "--toc-depth=2", f"--reference-doc={REFERENCE}",
            f"--metadata-file={METADATA}", f"--output={draft}"], json.dumps(document))
    office = subprocess.run(["/usr/bin/python3", str(OFFICE), str(draft.resolve()),
                             str((out / "sprawozdanie.docx").resolve()), str((out / "sprawozdanie.pdf").resolve())],
                            capture_output=True, text=True)
    if office.returncode:
        raise ReportError(f"LibreOffice: {office.stderr.strip()}")
