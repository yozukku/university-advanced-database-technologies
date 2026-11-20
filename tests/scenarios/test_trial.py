import pytest

from bench.scenarios.plugin import HASHED
from trial import COUNT, NEGATIVES, TRIALS

COUNT_INDEX = {"pg": "order_customer_created__idx", "mysql": "order_customer_created__idx",
               "mongo": "order_customer_created__idx", "neo4j": "Customer_id__uq"}


@pytest.mark.parametrize("scenario", TRIALS, ids=lambda scenario: scenario.id)
def test_trial(scenario, bench):
    bench.check(scenario)


@pytest.mark.parametrize("scenario", [COUNT], ids=lambda scenario: scenario.id)
def test_trial_plan(scenario, bench):
    for engine, index in COUNT_INDEX.items():
        for config in scenario.configs:
            assert index in bench.runs[(scenario.id, engine, config)].access["index"], (engine, config)


@pytest.mark.parametrize("scenario", NEGATIVES, ids=lambda scenario: scenario.id)
def test_oracle_rejects(scenario, bench, size):
    found = bench.problems(scenario)
    assert not found["errors"] and not found["metadata"], found
    assert found["probe"], "the key digest accepts the wrong rows"
    assert not found["affected"] and not found["commits"] and not found["union"], found
    if size in HASHED:
        assert found["rebuild"], "the canonical rebuild accepts the wrong rows"
        assert not found["coverage"], found
