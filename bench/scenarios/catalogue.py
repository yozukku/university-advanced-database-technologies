import argparse
import sys
import textwrap
from pathlib import Path

import yaml

from bench.scenarios.registry import ENGINES, JSON_ENGINES, OPS, load, read_ops

TARGET = Path("docs/bench/scenarios.md")
INDEXES = Path("docs/bench/indexes.yaml")
DDL = {"pg": Path("bench/ddl/pg/idx/indexes.sql"), "mysql": Path("bench/ddl/mysql/idx/indexes.sql"),
       "mongo": Path("bench/ddl/mongo/idx/indexes.json"), "neo4j": Path("bench/ddl/neo4j/idx/indexes.cypher")}
NAMES = {"pg": "PostgreSQL", "mysql": "MySQL", "mongo": "MongoDB", "neo4j": "Neo4j"}
QUERY_LANGUAGES = {"pg": "sql", "mysql": "sql", "mongo": "javascript", "neo4j": "cypher"}
DDL_LANGUAGES = {"pg": "sql", "mysql": "sql", "mongo": "json", "neo4j": "cypher"}
OPERATIONS = {"C": "tworzenie (INSERT)", "R": "odczyt (SELECT)", "U": "aktualizacja (UPDATE)", "D": "usuwanie (DELETE)"}
CORE_COUNT = 26
CORE_PER_OP = 6
JSON_COUNT = 6
H1 = {"H1-S": frozenset({"R4", "R5", "R6", "R7", "J2", "J4"}),
      "H1-I": frozenset({"C2", "C3", "C4", "C6", "J1"}),
      "H1-U": frozenset({"U1", "U5"})}
H1_OPS = {"H1-S": ("R", "SELECT"), "H1-I": ("C", "INSERT"), "H1-U": ("U", "UPDATE")}
NUANCES = frozenset({"U3", "J5"})


def is_json(scenario):
    return scenario.id.startswith("J")


def ids(registry, chosen):
    return ", ".join(scenario_id for scenario_id in registry if scenario_id in chosen) or "—"


def flags(scenario):
    return ", ".join(sorted(scenario.flags)) or "—"


def idx_indexes(plan, scenario):
    role = "serves" if scenario.read else "maintained_by"
    return ", ".join(name for name, row in plan.items() if scenario.id in row[role]) or "—"


def cell(text):
    return " ".join(text.split()).replace("|", "\\|")


def table(header, rows):
    return [f"| {' | '.join(header)} |", f"|{'---|' * len(header)}", *(f"| {' | '.join(row)} |" for row in rows)]


def objects(entry):
    if isinstance(entry, dict):
        return "—"
    return "; ".join(f"`{item['name']}` na `{item['scope']}` ({', '.join(f'`{key}`' for key in item['keys'])})"
                     for item in entry)


def settings(scenario_id):
    return ", ".join(f"`{key}: {'null' if value is None else value}`" for key, value in read_ops()[scenario_id].items())


def counted(scenarios):
    return ", ".join(f"{op} {sum(scenario.op == op for scenario in scenarios)}" for op in OPS)


def section(plan, scenario):
    lines = [f"### {scenario.id} — {OPERATIONS[scenario.op]}", "", cell(scenario.description), "",
             f"Flagi: {flags(scenario)}. Indeks IDX: {idx_indexes(plan, scenario)}. "
             f"Ustawienia z `ops.yaml`: {settings(scenario.id)}.", ""]
    for engine in scenario.engines:
        lines += [f"**{NAMES[engine]}**", "", f"```{QUERY_LANGUAGES[engine]}",
                  textwrap.dedent(scenario.impls[engine].text).strip("\n"), "```", ""]
    return lines


def render(registry):
    plan = yaml.safe_load(INDEXES.read_text())["idx"]
    core = [scenario for scenario in registry.values() if not is_json(scenario)]
    documents = [scenario for scenario in registry.values() if is_json(scenario)]
    lines = [
        "# Katalog scenariuszy", "",
        "Plik powstaje z rejestru `bench/scenarios/`, z `bench/scenarios/ops.yaml`, z `docs/bench/indexes.yaml` "
        "i ze skryptów `bench/ddl/<silnik>/idx/`. Nie edytuj go ręcznie: `make catalogue` zapisuje go od nowa, "
        "a `make catalogue CHECK=1` sprawdza katalog i zgodność pliku z rejestrem.", "",
        f"Scenariusze podstawowe: {len(core)} ({counted(core)}) we wszystkich czterech SZBD. "
        f"Scenariusze JSON: {len(documents)} ({counted(documents)}) w PostgreSQL, MySQL i MongoDB. "
        "Neo4j przechowuje `actor_` i `changes_` jako tekst JSON bez indeksów ścieżek, więc nie wykonuje serii J.", "",
        "Flagi: CX — złożony odczyt (złączenie, agregacja, przejście grafu albo zapytanie przestrzenne); "
        "BA — pomiar w konfiguracji BASE i IDX (pozostałe scenariusze tylko w IDX); "
        "H1-S, H1-I, H1-U — zbiory SELECT, INSERT i UPDATE hipotezy H1. "
        "Kolumna „Indeks IDX” podaje dla odczytu indeks, który go obsługuje, a dla zapisu indeksy, które zapis utrzymuje.", "",
        "Parametry: `%(nazwa)s` i `%s` w SQL, `$nazwa` w Cypher, `:nazwa` w wywołaniach MongoDB. "
        "`{marks}` i `{rows}` to listy znaczników, które adapter MySQL wstawia dla partii. "
        "`<…>` oznacza wartość, którą klient wylicza w mierzonej jednostce z wyniku poprzedniego kroku, "
        "albo słowny skrót fragmentu zapytania.", "",
        "## Przegląd", "",
        *table(("Id", "Operacja", "Opis", "Flagi", "Indeks IDX"),
               [(scenario.id, scenario.op, cell(scenario.description), flags(scenario), idx_indexes(plan, scenario))
                for scenario in registry.values()]),
        "", "## Zbiory hipotezy H1", "",
        *table(("Zbiór", "Operacja", "Scenariusze"),
               [*((flag, H1_OPS[flag][1], ids(registry, chosen)) for flag, chosen in H1.items()),
                ("poza werdyktem (BA)", "UPDATE", ids(registry, NUANCES))]),
        "", "## Scenariusze podstawowe", "",
    ]
    for scenario in core:
        lines += section(plan, scenario)
    lines += ["## Scenariusze JSON", ""]
    for scenario in documents:
        lines += section(plan, scenario)
    lines += ["## Indeksy IDX", "",
              *table(("Indeks", *(NAMES[engine] for engine in ENGINES), "Obsługuje", "Utrzymują"),
                     [(name, *(objects(row["engines"][engine]) for engine in ENGINES),
                       ", ".join(row["serves"]), ", ".join(row["maintained_by"])) for name, row in plan.items()]),
              ""]
    for engine in ENGINES:
        lines += [f"### {NAMES[engine]} — `{DDL[engine]}`", "", f"```{DDL_LANGUAGES[engine]}",
                  DDL[engine].read_text().strip("\n"), "```", ""]
    return "\n".join(lines)


def problems(registry, written):
    found = [f"{scenario.id}: {problem}" for scenario in registry.values() for problem in scenario.problems()]
    core = [scenario for scenario in registry.values() if not is_json(scenario)]
    documents = [scenario for scenario in registry.values() if is_json(scenario)]
    if len(core) != CORE_COUNT:
        found.append(f"{len(core)} core scenarios, expected {CORE_COUNT}")
    found += [f"{count} core {op} scenarios, expected at least {CORE_PER_OP}" for op in OPS
              if (count := sum(scenario.op == op for scenario in core)) < CORE_PER_OP]
    if len(documents) != JSON_COUNT:
        found.append(f"{len(documents)} JSON scenarios, expected {JSON_COUNT}")
    for scenario in registry.values():
        wanted = JSON_ENGINES if is_json(scenario) else ENGINES
        texts = tuple(engine for engine, impl in scenario.impls.items() if impl.text.strip())
        if sorted(texts) != sorted(wanted):
            found.append(f"{scenario.id}: query texts for {', '.join(texts)}, expected {', '.join(wanted)}")
    for flag, chosen in H1.items():
        flagged = {scenario.id for scenario in registry.values() if flag in scenario.flags}
        if flagged != chosen:
            found.append(f"{flag} flags {sorted(flagged)}, fixed set {sorted(chosen)}")
        found += [f"{scenario_id}: {flag} needs op {H1_OPS[flag][0]}" for scenario_id in sorted(chosen)
                  if scenario_id in registry and registry[scenario_id].op != H1_OPS[flag][0]]
    measured = {scenario.id for scenario in registry.values() if "BA" in scenario.flags}
    wanted = frozenset().union(*H1.values()) | NUANCES
    if measured != wanted:
        found.append(f"BA flags {sorted(measured)}, expected the H1 sets and {sorted(NUANCES)}: {sorted(wanted)}")
    if written != render(registry):
        found.append(f"{TARGET} is out of date, run make catalogue")
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    registry = load()
    if not args.check:
        TARGET.write_text(render(registry))
        print(f"{TARGET}: {len(registry)} scenarios")
        return
    found = problems(registry, TARGET.read_text() if TARGET.exists() else None)
    if found:
        sys.exit("Catalogue check failed:\n  " + "\n  ".join(found))
    core = [scenario for scenario in registry.values() if not is_json(scenario)]
    print(f"Catalogue OK: {len(core)} core ({counted(core)}), {len(registry) - len(core)} JSON, "
          f"BA = H1 {len(frozenset().union(*H1.values()))} + {len(NUANCES)} nuances, {TARGET} up to date")


if __name__ == "__main__":
    main()
