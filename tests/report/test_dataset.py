import json
import re
import struct
from pathlib import Path

from bench.report import dataset, document
from bench.report.document import MISSING

TRANSFORM = Path("bench/transform/neo4j/transform.py")
GRAPH = Path("report/assets/graph/model.svg")
ASSETS = Path("report/assets")


def load_file(results, size, total, differ=(), distance=251.5):
    tables = dataset.tables()
    counts = {table: 1 for table in tables}
    counts[tables[-1]] = total - len(tables) + 1
    canonical = {table: {"rows": counts[table], "hash": f"{index:064x}"} for index, table in enumerate(tables)}
    engines = {engine: {"tables": {table: dict(value) for table, value in canonical.items()}, "distance_km": distance,
                        "load_seconds": 1234.5, "disk_bytes": 2_500_000} for engine in dataset.ENGINES}
    for engine, table in differ:
        engines[engine]["tables"][table]["hash"] = "f" * 64
    path = Path(results) / "load" / f"{size}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"size": size, "canonical": {"tables": canonical}, "engines": engines}))


def rows(markdown):
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in markdown.splitlines()]


def width(png):
    return struct.unpack(">I", png.read_bytes()[16:20])[0]


def test_volume_lists_present_sizes_with_exact_totals(tmp_path):
    load_file(tmp_path, "M", 1_000_000)
    load_file(tmp_path, "S", 500_000)
    (tmp_path / "load" / "L.json").write_text(json.dumps({"engines": {"pg": {"load_seconds": 1}}}))
    table = rows(dataset.volume(tmp_path))
    assert table[0] == ["Tabela", "S", "M"]
    assert [row[0] for row in table[2:-1]] == [f"`{name}`" for name in dataset.tables()]
    assert len(table[2:-1]) == 13 and table[2][0] == "`lockermat_`" and table[-2][0] == "`audit_event_`"
    assert table[-1] == ["**Razem**", "**500 000**", "**1 000 000**"]


def test_dataset_tables_render_brak_danych_without_load_results(tmp_path):
    for name in ("volume", "parity", "load"):
        text = document.resolve(f'{{{{ dataset("{name}", "Podpis") }}}}', tmp_path, "x.md")
        assert MISSING in text and f"{{#tab:{name}}}" in text


def test_parity_shows_common_hash_or_the_differing_engines(tmp_path):
    load_file(tmp_path, "S", 500_000, differ=[("mysql", "order_"), ("neo4j", "order_")], distance=251.62)
    table = {row[0]: row[1:] for row in rows(dataset.parity(tmp_path))}
    assert table["`lockermat_`"] == ["`000000000000`"]
    assert table["`order_`"] == ["różne: MySQL, Neo4j"]
    assert table["Odległość Kraków Główny – Warszawa Centralna [km]"] == ["251,6–251,6"]


def test_load_table_formats_polish_numbers(tmp_path):
    load_file(tmp_path, "S", 500_000)
    table = rows(dataset.loading(tmp_path))
    assert table[0] == ["SZBD", "S: ładowanie [s]", "S: dysk [MB]"]
    assert table[2] == ["PostgreSQL", "1 234,5", "2,5"]


def test_type_table_lists_only_translated_column_types():
    table = {row[0]: row[1:] for row in rows(dataset.types(None))[2:]}
    assert table["`timestamptz`"][0] == "`datetime(3)`"
    assert table["`jsonb`"] == ["`json`", "2"]
    assert table["`geometry(point, 4326)`"][0] == "`point srid 4326`"
    assert "`bigint`" not in table and "`text`" not in table


def test_object_table_maps_exclusions_partial_indexes_and_json_indexes():
    text = dataset.objects(None)
    assert text.count(" EXCLUDE") == 5
    assert text.count("wyzwalacz BEFORE INSERT") == 5 and text.count("wyzwalacz BEFORE UPDATE") == 5
    assert "`payment_incident__fk` automatyczny indeks klucza obcego" in text
    assert "`reservation_leg__uq` unikalny indeks funkcyjny" in text
    assert "`jx2__idx` indeks wielowartościowy" in text and "`excl_guard_` tabela" in text
    assert "`lockermat__pkey`" not in text and "__ck`" not in text


def test_samples_render_mongo_documents():
    order = dataset.sample("order")
    assert order.startswith("{\n  _id: 17,") and "reservations: [" in order and "… (jeszcze 1)" in order
    assert "createdAt: ISODate('2024-11-21T06:30:24.000Z')" in order and "$numberLong" not in order
    audit = dataset.sample("audit")
    assert "{ f: 'status_', new: 'AWAITING_PAYMENT', old: null }" in audit and "…" not in audit
    text = document.resolve('{{ sample("audit", "Zdarzenie") }}', None, "x.md")
    assert text.startswith("::: {#fig:audit .figure .listing}\n```\n{") and text.endswith("\n```\n\nZdarzenie\n:::")


def test_graph_figure_names_every_label_and_relationship_type():
    source = TRANSFORM.read_text(encoding="utf-8")
    labels = re.findall(r'^ {4}"(\w+)": "\w+_",$', source, re.MULTILINE)
    types = re.findall(r'^ {8}\("([A-Z_]+)", "\w+_"', source, re.MULTILINE) + ["SHIPS_TO"]
    drawn = re.sub(r"<style>.*?</style>|<[^>]+>", " ", GRAPH.read_text(encoding="utf-8"), flags=re.DOTALL)
    texts = set(re.findall(r"\w+", drawn))
    assert len(labels) == 13 and len(types) == 15
    assert set(labels) <= texts and set(types) <= texts


def test_committed_figures_are_wide_enough():
    names = ["legenda", "przeglad", "siec-automatow", "klient-i-pieniadze", "zamowienie-i-rezerwacja",
             "dostep-i-incydenty", "dziennik-zdarzen"]
    figures = [ASSETS / "erd" / f"{name}.png" for name in names] + [ASSETS / "graph" / "model.png"]
    assert all(width(path) >= 2000 for path in figures)
