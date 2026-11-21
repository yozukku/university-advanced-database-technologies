import pytest
from bson import json_util

from bench.check.verify.results import directory
from bench.scenarios import oracle
from bench.scenarios.create.booking import checked
from bench.scenarios.params import dataset
from bench.scenarios.registry import load

REGISTRY = load()
BOOKING, SHIPMENT, UPSERT, OVERSTAY = (REGISTRY[key] for key in ("C3", "C4", "C5", "C6"))
OVERLAPS = """
with legs as (
    select id_, cell_id_, epoch_ms(from_) as from_, epoch_ms(to_) as to_ from reservation_
    where status_ in ('BOOKED', 'OCCUPIED')
    union all
    select id_, cell_id_, from_, to_ from booked
)
select count(*) from legs a join legs b on a.cell_id_ = b.cell_id_ and a.id_ < b.id_
where a.from_ < b.to_ and b.from_ < a.to_
"""


def test_c3_mysql_rejects_a_short_digest():
    with pytest.raises(ValueError, match="31 bytes"):
        checked(bytes(31))
    assert checked(bytes(32)) == bytes(32)


@pytest.mark.parametrize("scenario", [BOOKING], ids=[BOOKING.id])
def test_booking_leaves_no_overlap(scenario, bench):
    columns = [name for name, _ in bench.schema["reservation_"]]
    with dataset(bench.size) as (db, _):
        for label, run in bench.labelled(scenario).items():
            assert run.error is None, f"{label}: {run.error}"
            legs = run.probe["reservation_"]
            assert not legs["changed"] and not legs["deleted"], label
            booked = [dict(zip(columns, values, strict=True)) for _, values in legs["inserted"]]
            assert len(booked) == scenario.config(bench.size)["count"], label
            assert {leg["status_"] for leg in booked} == {"BOOKED"}, label
            db.execute("create or replace temp table booked (id_ bigint, cell_id_ bigint, from_ bigint, to_ bigint)")
            db.executemany("insert into booked values (?, ?, ?, ?)",
                           [(leg["id_"], leg["cell_id_"], leg["from_"], leg["to_"]) for leg in booked])
            [(overlaps,)] = db.execute(OVERLAPS).fetchall()
            assert overlaps == 0, f"{label}: {overlaps} overlapping live legs"


@pytest.mark.parametrize("scenario", [SHIPMENT], ids=[SHIPMENT.id])
def test_c4_writes_the_derived_link(scenario, bench):
    with dataset(bench.size) as (db, _):
        lockers = dict(db.execute("select id_, lockermat_id_ from lockermat_cell_").fetchall())
    columns = {table: [name for name, _ in bench.schema[table]] for table in ("order_", "reservation_")}
    for config in scenario.configs:
        for engine in ("mongo", "neo4j"):
            run = bench.runs[(scenario.id, engine, config)]
            assert run.error is None, f"{engine}/{config}: {run.error}"
            rows = {table: [dict(zip(names, values, strict=True)) for _, values in run.probe[table]["inserted"]]
                    for table, names in columns.items()}
            legs = {(leg["order_id_"], leg["leg_"]): lockers[leg["cell_id_"]] for leg in rows["reservation_"]}
            expected = sorted([order["id_"], legs[order["id_"], "ORIGIN"], legs[order["id_"], "DESTINATION"],
                               order["created_at_"]] for order in rows["order_"])
            assert len(expected) == scenario.config(bench.size)["count"], f"{engine}/{config}"
            for name, links in run.after.items():
                assert links == expected, f"{engine}/{config} {name}"


@pytest.mark.parametrize("scenario", [UPSERT], ids=[UPSERT.id])
def test_c5_inserts_half_and_updates_half(scenario, bench):
    half = scenario.config(bench.size)["count"] // 2
    for label, run in bench.labelled(scenario).items():
        assert run.error is None, f"{label}: {run.error}"
        assert oracle.affected(run.probe) == {"customer_": {"inserted": half, "changed": half, "deleted": 0}}, label


@pytest.mark.parametrize("scenario", [OVERSTAY], ids=[OVERSTAY.id])
def test_c6_discovery_plans_and_tariffs(scenario, bench):
    runs = bench.labelled(scenario)
    assert all(run.error is None for run in runs.values()), {label: run.error for label, run in runs.items()}
    with dataset(bench.size) as (db, _):
        [(tariffs,)] = db.execute("select count(*) from tariff_").fetchall()
    for config in scenario.configs:
        assert runs[f"mongo/{config}"].outcome.driver_counts["tariffs"] == tariffs, config
    assert "reservation_overdue__idx" in runs["mysql/base"].access["index"], runs["mysql/base"].access
    stored = directory(bench.size).parent / "explain" / f"{scenario.id}-discovery-mongo-base.json"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_text(json_util.dumps(runs["mongo/base"].plan, indent=2) + "\n")
    assert json_util.loads(stored.read_text())["queryPlanner"]["winningPlan"]
