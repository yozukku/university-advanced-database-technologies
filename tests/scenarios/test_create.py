import pytest

from bench.scenarios.create.booking import checked
from bench.scenarios.params import dataset
from bench.scenarios.registry import load

BOOKING = load()["C3"]
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
