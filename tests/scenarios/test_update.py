import pytest

from bench.check.verify.canonical import milliseconds
from bench.scenarios.params import dataset
from bench.scenarios.registry import load

REGISTRY = load()
CLOSING, REDEMPTION, EXPIRY = (REGISTRY[key] for key in ("U1", "U2", "U3"))
GRANTS = """
select x.id_, a.id_, a.reservation_id_, epoch_ms(x.requested_at_)
from cell_opening_ x join access_code_ a on a.id_ = x.access_code_id_
where list_contains(?, x.id_)
"""
UNPAID = """
select o.id_, r.id_
from order_ o left join reservation_ r on r.order_id_ = o.id_ and r.status_ = 'BOOKED'
where o.status_ = 'AWAITING_PAYMENT' and o.payment_deadline_ < getvariable('benchmark_t0')
"""


def changed(entries):
    return {table: {"inserted": [], "changed": sorted([key, change] for key, change in rows), "deleted": []}
            for table, rows in entries.items()}


def closing(db, profile, params):
    closed = {"status_": ["PAID", "COMPLETED"], "closed_at_": [None, milliseconds(profile.t0)]}
    return changed({"order_": [(order, closed) for batch in params["orders"] for order in batch]})


def redemption(db, profile, params):
    rows = db.execute(GRANTS, [[opening for batch in params for opening in batch]]).fetchall()
    return changed({
        "cell_opening_": [(opening, {"result_": ["PENDING", "OPENED"]}) for opening, _, _, _ in rows],
        "access_code_": [(code, {"status_": ["ACTIVE", "USED"], "used_at_": [None, at]}) for _, code, _, at in rows],
        "reservation_": [(leg, {"status_": ["BOOKED", "OCCUPIED"], "deposited_at_": [None, at]})
                         for _, _, leg, at in rows],
    })


def expiry(db, profile, params):
    rows = db.execute(UNPAID).fetchall()
    expired = {"status_": ["AWAITING_PAYMENT", "EXPIRED"], "closed_at_": [None, milliseconds(profile.t0)]}
    return changed({
        "order_": [(order, expired) for order in sorted({order for order, _ in rows})],
        "reservation_": [(leg, {"status_": ["BOOKED", "CANCELLED"]}) for _, leg in rows if leg is not None],
    })


ANSWERS = {"U1": closing, "U2": redemption, "U3": expiry}


@pytest.mark.parametrize("scenario", [CLOSING, REDEMPTION, EXPIRY], ids=list(ANSWERS))
def test_changes_equal_the_canonical_answer(scenario, bench):
    with dataset(bench.size) as (db, profile):
        expected = ANSWERS[scenario.id](db, profile, bench.params[scenario.id])
    assert all(entry["changed"] for entry in expected.values()), expected.keys()
    for label, run in bench.labelled(scenario).items():
        assert run.error is None, f"{label}: {run.error}"
        assert run.probe == expected, label


@pytest.mark.parametrize("scenario", [EXPIRY], ids=[EXPIRY.id])
def test_u3_mysql_base_discovery_uses_the_case_index(scenario, bench):
    run = bench.runs[(scenario.id, "mysql", "base")]
    assert run.error is None, run.error
    assert "order_awaiting_payment__idx" in run.access["index"], run.access
