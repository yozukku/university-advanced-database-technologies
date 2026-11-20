import pytest

from bench.scenarios.registry import load

REGISTRY = load()


@pytest.mark.parametrize("scenario", REGISTRY.values(), ids=REGISTRY.keys())
def test_scenario(scenario, bench):
    bench.check(scenario)
