import argparse

from .parquet import connect, require_empty
from bench.gen.plan import make_plan
from bench.gen.profiles import load_profile


TABLES = ("lockermat_cell_", "customer_", "order_", "reservation_", "shipment_", "tariff_")
CHECKS = {
    "booking overlaps": """
        select count(*) from (
            select from_, max(to_) over (
                partition by cell_id_ order by from_, id_
                rows between unbounded preceding and 1 preceding
            ) as previous_end
            from reservation_ where status_ in ('BOOKED', 'OCCUPIED')
        ) where from_ < previous_end
    """,
    "actual occupancy overlaps": """
        select count(*) from (
            select deposited_at_, max(coalesce(collected_at_, 'infinity'::timestamptz)) over (
                partition by cell_id_ order by deposited_at_, id_
                rows between unbounded preceding and 1 preceding
            ) as previous_end
            from reservation_ where deposited_at_ is not null
        ) where deposited_at_ < previous_end
    """,
    "order chronology": """
        select count(*) from order_ o
        left join customer_ c on c.id_ = o.customer_id_
        left join tariff_ t on t.id_ = o.tariff_id_ and t.size_ = o.size_
        where c.id_ is null or t.id_ is null or o.created_at_ < c.created_at_
           or o.created_at_ < t.valid_from_ or o.created_at_ >= t.valid_to_
           or o.payment_deadline_ <= o.created_at_ or o.closed_at_ < o.created_at_
           or (o.closed_at_ is not null) != (o.status_ in ('COMPLETED', 'CANCELLED', 'EXPIRED'))
    """,
    "reservation chronology and keys": """
        select count(*) from reservation_ r
        left join order_ o on o.id_ = r.order_id_ and o.type_ = r.order_type_ and o.size_ = r.size_
        left join lockermat_cell_ c on c.id_ = r.cell_id_ and c.size_ = r.size_
        where o.id_ is null or c.id_ is null or r.to_ <= r.from_ or r.from_ <= o.created_at_
           or (r.deposited_at_ is not null) != (r.status_ in ('OCCUPIED', 'COMPLETED'))
           or (r.collected_at_ is not null) != (r.status_ = 'COMPLETED') or r.collected_at_ < r.deposited_at_
    """,
    "shipment legs and chronology": """
        select count(*) from shipment_ s
        left join order_ o on o.id_ = s.order_id_ and o.type_ = s.order_type_
        left join reservation_ r on r.order_id_ = s.order_id_ and r.leg_ = 'ORIGIN'
        left join reservation_ d on d.order_id_ = s.order_id_ and d.leg_ = 'DESTINATION'
        left join lockermat_cell_ rc on rc.id_ = r.cell_id_
        left join lockermat_cell_ dc on dc.id_ = d.cell_id_
        where o.id_ is null or r.id_ is null or d.id_ is null or rc.lockermat_id_ = dc.lockermat_id_
           or (d.deposited_at_ is not null and (
               r.collected_at_ is null or d.deposited_at_ < r.collected_at_
           ))
    """,
    "orders with multiple occupied legs": """
        select count(*) from (
            select order_id_ from reservation_ where status_ = 'OCCUPIED' group by order_id_ having count(*) > 1
        )
    """,
}


def check_bookings(db, profile, plan):
    require_empty(db, CHECKS)
    for name in TABLES:
        actual = db.execute(f"select count(*) from {name}").fetchone()[0]
        if actual != plan.counts[name]:
            raise ValueError(f"{name}: expected {plan.counts[name]} rows, found {actual}")
    heavy = db.execute("""
        select count(*) from (select customer_id_ from order_ group by customer_id_ having count(*) between 60 and 80)
    """).fetchone()[0]
    expected = plan.counts["customer_"] // 100
    if heavy != expected:
        raise ValueError(f"Expected {expected} heavy customers, found {heavy}")
    repeated = db.execute("""
        select count(*) from (select recipient_phone_ from shipment_ group by recipient_phone_ having count(*) > 1)
    """).fetchone()[0]
    if not repeated:
        raise ValueError("No reused shipment recipient phones")
    closed, total = db.execute("""
        select count(*) filter (where closed_at_ is not null), count(*)
        from order_ where created_at_ < ? - interval '30 days'
    """, [profile.t0]).fetchone()
    if closed <= total // 2:
        raise ValueError(f"Only {closed} of {total} orders older than 30 days are closed")
    print(f"{profile.size}: zero overlaps or chronology violations, {heavy} heavy customers, {repeated} reused phones")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    args = parser.parse_args()
    profile = load_profile(args.size)
    with connect(profile.destination, TABLES) as db:
        check_bookings(db, profile, make_plan(profile))


if __name__ == "__main__":
    main()
