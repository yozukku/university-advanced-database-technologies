import json
import re
from datetime import datetime, timezone
from pathlib import Path

SIZES = ("XS", "S", "M", "L")
ENGINES = {"pg": "PostgreSQL", "mysql": "MySQL", "mongo": "MongoDB", "neo4j": "Neo4j"}
SCHEMA = Path("docs/design/schema.sql")
INDEXES = Path("docs/bench/indexes.yaml")
DDL = {engine: Path(f"bench/ddl/{engine}/base/tables.sql") for engine in ("pg", "mysql")}
SAMPLES = {"order": Path("bench/load/tests/golden/shipment_order.json"),
           "audit": Path("bench/load/tests/golden/audit_event.json")}
CREATE_TABLE = re.compile(r"^create table (\w+)", re.MULTILINE)
COLUMN = re.compile(r"^ {4}(\w+_)\s+(.+?)(?=\s+(?:not null|null|default|generated|srid|primary key)\b|,?\s*$)")
SRID = re.compile(r"\bsrid (\d+)")
KINDS = {
    "exclude": "EXCLUDE", "btree": "indeks B-drzewo", "unique": "UNIQUE", "gist": "indeks GiST", "gin": "indeks GIN",
    "functional": "indeks funkcyjny", "fulltext": "indeks FULLTEXT", "spatial": "indeks SPATIAL",
    "multi_valued": "indeks wielowartościowy", "trigger": "wyzwalacz", "table": "tabela", "column": "kolumna",
    "primary": "klucz główny",
}
INLINE = 72
NBSP = " "


def number(value, digits=0):
    return f"{value:,.{digits}f}".replace(",", NBSP).replace(".", ",")


def markdown(header, rows, widths=None):
    separator = widths or ["---"] + ["--:"] * (len(header) - 1)
    lines = [header, separator, *rows]
    return "\n".join("| " + " | ".join(cells) + " |" for cells in lines)


def loads(results):
    found = {}
    for size in SIZES:
        path = Path(results) / "load" / f"{size}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if "canonical" in data:
                found[size] = data
    return found


def tables():
    return CREATE_TABLE.findall(SCHEMA.read_text(encoding="utf-8"))


def volume(results):
    found = loads(results)
    if not found:
        return None
    rows = [[f"`{table}`", *(number(data["canonical"]["tables"][table]["rows"]) for data in found.values())]
            for table in tables()]
    totals = [sum(data["canonical"]["tables"][table]["rows"] for table in tables()) for data in found.values()]
    rows.append(["**Razem**", *(f"**{number(total)}**" for total in totals)])
    return markdown(["Tabela", *found], rows)


def agreement(data, table):
    expected = data["canonical"]["tables"][table]["hash"]
    differ = [name for engine, name in ENGINES.items()
              if data.get("engines", {}).get(engine, {}).get("tables", {}).get(table, {}).get("hash") != expected]
    return f"różne: {', '.join(differ)}" if differ else f"`{expected[:12]}`"


def distance(data):
    values = [data["engines"][engine]["distance_km"] for engine in ENGINES
              if data.get("engines", {}).get(engine, {}).get("distance_km") is not None]
    return f"{number(min(values), 1)}–{number(max(values), 1)}" if values else "—"


def parity(results):
    found = loads(results)
    if not found:
        return None
    rows = [[f"`{table}`", *(agreement(data, table) for data in found.values())] for table in tables()]
    rows.append(["Odległość Kraków Główny – Warszawa Centralna [km]", *(distance(data) for data in found.values())])
    return markdown(["Tabela", *found], rows, ["---"] * (len(found) + 1))


def measured(data, engine, key, scale, digits):
    value = data.get("engines", {}).get(engine, {}).get(key)
    return "—" if value is None else number(value / scale, digits)


def loading(results):
    found = loads(results)
    if not found:
        return None
    header = ["SZBD"]
    for size in found:
        header += [f"{size}: ładowanie [s]", f"{size}: dysk [MB]"]
    rows = []
    for engine, name in ENGINES.items():
        cells = [name]
        for data in found.values():
            cells += [measured(data, engine, "load_seconds", 1, 1), measured(data, engine, "disk_bytes", 1_000_000, 1)]
        rows.append(cells)
    return markdown(header, rows)


def columns(engine):
    found, table = {}, None
    for line in DDL[engine].read_text(encoding="utf-8").splitlines():
        if created := CREATE_TABLE.match(line):
            table = created.group(1)
        elif column := COLUMN.match(line):
            srid = SRID.search(line)
            found[table, column.group(1)] = column.group(2) + (f" srid {srid.group(1)}" if srid else "")
    return found


def types(results):
    pg, mysql = columns("pg"), columns("mysql")
    pairs = {}
    for key, source in pg.items():
        target = mysql[key]
        if source.replace(" ", "").lower() != target.replace(" ", "").lower():
            pairs[source, target] = pairs.get((source, target), 0) + 1
    rows = [[f"`{source}`", f"`{target}`", number(count)] for (source, target), count in pairs.items()]
    return markdown(["PostgreSQL 17", "MySQL 8.4", "Kolumny"], rows, ["---", "---", "--:"])


def kind(item):
    words = KINDS.get(item["kind"], item["kind"])
    if item["kind"] == "functional" and item.get("unique"):
        words = "unikalny indeks funkcyjny"
    if item["kind"] == "trigger":
        words += f" {item['event'].upper()}"
    if item.get("parser"):
        words += f" ({item['parser']})"
    if item.get("opclass"):
        words += f" ({item['opclass']})"
    if item.get("predicate") and item["kind"] in ("btree", "unique", "exclude"):
        words += " z warunkiem WHERE"
    return f"`{item['name']}` {words}"


def automatic(index, item):
    for candidate in index["mysql_fk_support"].values():
        if candidate["scope"] == item["scope"] and candidate["keys"][0] == item["keys"][0]:
            return f"`{candidate['name']}` automatyczny indeks klucza obcego"
    return "—"


def objects(results):
    index = json.loads(INDEXES.read_text(encoding="utf-8"))
    entries = [*index["base"].values(), *index["base_extras"].values(),
               *(entry["engines"] for entry in index["idx"].values())]
    rows = []
    for entry in entries:
        pg, mysql = entry["pg"], entry["mysql"]
        if isinstance(pg, dict) and isinstance(mysql, dict):
            continue
        if isinstance(pg, list) and isinstance(mysql, list) and [item["kind"] for item in pg] == [
                item["kind"] for item in mysql] and not any(item.get("predicate") for item in pg):
            continue
        scope = (pg if isinstance(pg, list) else mysql)[0]["scope"]
        source = ", ".join(map(kind, pg)) if isinstance(pg, list) else "—"
        target = ", ".join(map(kind, mysql)) if isinstance(mysql, list) else automatic(index, pg[0])
        rows.append([f"`{scope}`", source, target])
    return markdown(["Tabela", "PostgreSQL 17", "MySQL 8.4"], rows, ["----", "------", "-------"])


def instant(milliseconds):
    moment = datetime.fromtimestamp(int(milliseconds) / 1000, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def scalar(value):
    if isinstance(value, dict):
        if "$numberLong" in value:
            return value["$numberLong"]
        if "$numberInt" in value:
            return value["$numberInt"]
        if "$date" in value:
            return f"ISODate('{instant(value['$date']['$numberLong'])}')"
        if "$binary" in value:
            return f"BinData({int(value['$binary']['subType'], 16)}, '{value['$binary']['base64']}')"
        return None
    if isinstance(value, list):
        return "[]" if not value else None
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return "'" + value.replace("'", "\\'") + "'"
    return str(value)


def shell(value, depth=0):
    simple = scalar(value)
    if simple is not None:
        return simple
    pad = "  " * depth
    if isinstance(value, list):
        lines = [f"{pad}  {shell(value[0], depth + 1)}"]
        if len(value) > 1:
            lines[0] += ","
            lines.append(f"{pad}  … (jeszcze {len(value) - 1})")
        return "[\n" + "\n".join(lines) + f"\n{pad}]"
    items = [(key, scalar(item)) for key, item in value.items()]
    if all(text is not None for _, text in items):
        inline = "{ " + ", ".join(f"{key}: {text}" for key, text in items) + " }"
        if len(pad) + len(inline) <= INLINE:
            return inline
    lines = [f"{pad}  {key}: {shell(item, depth + 1)}" for key, item in value.items()]
    return "{\n" + ",\n".join(lines) + f"\n{pad}}}"


def sample(name):
    return shell(json.loads(SAMPLES[name].read_text(encoding="utf-8")))


TABLES = {"volume": volume, "parity": parity, "load": loading, "types": types, "objects": objects}
