import pytest

from bench.scenarios.registry import load

REGISTRY = load()
D2 = REGISTRY["D2"]
PURGES = [REGISTRY[key] for key in ("D4", "D5", "D6")]


def nothing_left(scenario, bench):
    left = {engine: bench.runs[(scenario.id, engine, "idx")].after for engine in scenario.engines}
    assert all(counts and not any(counts.values()) for counts in left.values()), left


@pytest.mark.parametrize("scenario", [D2], ids=[D2.id])
def test_no_dependants_left(scenario, bench):
    nothing_left(scenario, bench)


@pytest.mark.parametrize("scenario", PURGES, ids=[scenario.id for scenario in PURGES])
def test_no_orphans_left(scenario, bench):
    nothing_left(scenario, bench)
