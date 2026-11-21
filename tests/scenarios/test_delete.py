import pytest

from bench.scenarios.registry import load

D2 = load()["D2"]


@pytest.mark.parametrize("scenario", [D2], ids=[D2.id])
def test_no_dependants_left(scenario, bench):
    left = {engine: bench.runs[(scenario.id, engine, "idx")].after for engine in scenario.engines}
    assert all(counts and not any(counts.values()) for counts in left.values()), left
