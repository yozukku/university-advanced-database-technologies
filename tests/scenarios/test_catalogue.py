from dataclasses import replace

from bench.scenarios.catalogue import TARGET, problems, render
from bench.scenarios.registry import load


def changed(registry, scenario_id, **fields):
    return registry | {scenario_id: replace(registry[scenario_id], **fields)}


def test_catalogue_is_complete_and_current():
    assert problems(load(), TARGET.read_text()) == []


def test_catalogue_rejects_a_flag_outside_the_fixed_sets():
    registry = load()
    nuance = changed(registry, "U3", flags=frozenset())
    assert [found for found in problems(nuance, render(nuance)) if found.startswith("BA flags")]
    moved = changed(registry, "R2", flags=frozenset({"BA", "H1-S"}))
    found = problems(moved, render(moved))
    assert [line for line in found if line.startswith("H1-S flags")]
    assert [line for line in found if line.startswith("BA flags")]


def test_catalogue_rejects_a_missing_query_text():
    registry = load()
    scenario = registry["J1"]
    missing = changed(registry, "J1", impls={engine: impl for engine, impl in scenario.impls.items() if engine != "mongo"})
    assert [found for found in problems(missing, render(missing)) if found.startswith("J1: query texts")]


def test_catalogue_rejects_a_stale_file():
    registry = load()
    assert problems(registry, render(registry).replace("RODO art. 15", "RODO art. 16")) == [
        f"{TARGET} is out of date, run make catalogue"]
