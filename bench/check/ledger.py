import argparse

from bench.gen.plan import make_plan
from bench.gen.profiles import load_profile
from bench.gen.slices import exact_slices

from .bookings import check_bookings
from .parquet import connect, require_empty


TABLES = (
    "lockermat_", "lockermat_opening_hours_", "lockermat_cell_", "tariff_", "customer_", "order_", "reservation_",
    "shipment_", "access_code_", "payment_", "incident_", "cell_opening_",
)
CHECKS = {
    "invalid code or code usage": """
        select count(*) from access_code_ a
        left join reservation_ r on r.id_ = a.reservation_id_
        where r.id_ is null or a.valid_from_ < r.from_ or a.valid_to_ > r.to_
           or a.valid_to_ <= a.valid_from_ or a.created_at_ >= a.valid_to_ or octet_length(a.code_hmac_) != 32
           or (a.used_at_ is not null) != (a.status_ = 'USED')
           or a.used_at_ < a.valid_from_ or a.used_at_ >= a.valid_to_ or a.used_at_ < a.created_at_
           or (a.used_at_ is not null and a.used_at_ is distinct from
               case when a.purpose_ = 'DROP_OFF' then r.deposited_at_ else r.collected_at_ end)
    """,
    "active code purpose overlaps": """
        select count(*) from (
            select valid_from_, max(valid_to_) over (
                partition by reservation_id_, purpose_ order by valid_from_, id_
                rows between unbounded preceding and 1 preceding
            ) as previous_end
            from access_code_ where status_ = 'ACTIVE'
        ) where valid_from_ < previous_end
    """,
    "reused HMACs": "select count(*) - count(distinct code_hmac_) from access_code_",
    "invalid door journal rows": """
        select count(*) from cell_opening_ c
        left join access_code_ a on a.id_ = c.access_code_id_
        left join incident_ i on i.id_ = c.incident_id_
        where (c.access_code_id_ is null) = (c.incident_id_ is null)
           or (c.incident_id_ is not null) != (c.channel_ = 'SERVICE')
           or (c.channel_ = 'KEYPAD') != (c.actor_keycloak_id_ is null)
           or c.closed_at_ < c.requested_at_ or (c.closed_at_ is not null and c.result_ != 'OPENED')
           or (c.access_code_id_ is not null and (a.id_ is null or c.requested_at_ < a.created_at_
               or c.requested_at_ < a.valid_from_ or c.requested_at_ >= a.valid_to_))
           or (c.incident_id_ is not null and (i.id_ is null or c.requested_at_ < i.created_at_))
           or (c.result_ = 'OPENED' and a.id_ is not null and a.used_at_ is distinct from c.requested_at_)
           or (c.result_ = 'PENDING' and (a.status_ != 'ACTIVE' or a.id_ is null))
           or c.requested_at_ >= getvariable('benchmark_t0')
    """,
    "multiple live openings": """
        select count(*) from (
            select access_code_id_ from cell_opening_ where access_code_id_ is not null
                and result_ in ('PENDING', 'OPENED') group by access_code_id_ having count(*) > 1
        )
    """,
    "pending drop-offs cannot be redeemed": """
        select count(*) from cell_opening_ c
        join access_code_ a on a.id_ = c.access_code_id_
        join reservation_ r on r.id_ = a.reservation_id_
        join order_ o on o.id_ = r.order_id_
        where c.result_ = 'PENDING' and (
            a.purpose_ != 'DROP_OFF' or r.status_ != 'BOOKED' or o.status_ != 'PAID'
            or exists (
                select 1 from reservation_ live where live.cell_id_ = r.cell_id_
                    and live.deposited_at_ <= c.requested_at_
                    and (live.collected_at_ is null or live.collected_at_ > c.requested_at_)
            )
        )
    """,
    "invalid payments": """
        select count(*) from payment_ p
        left join order_ o on o.id_ = p.order_id_
        left join payment_ c on c.refundable_id_ = p.refund_of_id_
            and c.order_id_ = p.order_id_ and c.provider_ = p.provider_
        where o.id_ is null or p.amount_ <= 0 or p.created_at_ < o.created_at_
           or p.created_at_ >= getvariable('benchmark_t0') or p.completed_at_ < p.created_at_
           or (p.status_ = 'COMPLETED') != (p.completed_at_ is not null)
           or (p.status_ = 'COMPLETED' and p.provider_ref_ is null)
           or (p.kind_ = 'REFUND' and (c.id_ is null or c.completed_at_ >= p.created_at_))
           or p.refundable_id_ is distinct from
               case when p.kind_ in ('CHARGE', 'EXTENSION', 'OVERSTAY') and p.status_ = 'COMPLETED' then p.id_ end
    """,
    "refund ceilings": """
        select count(*) from (
            select p.refund_of_id_ from payment_ p join payment_ c on c.refundable_id_ = p.refund_of_id_
            where p.kind_ = 'REFUND' and p.status_ in ('COMPLETED', 'PENDING')
            group by p.refund_of_id_, c.amount_ having sum(p.amount_) > c.amount_
        )
    """,
    "duplicate provider references": """
        select count(*) from (
            select provider_, provider_ref_ from payment_ where provider_ref_ is not null
            group by provider_, provider_ref_ having count(*) > 1
        )
    """,
    "invalid incident links": """
        select count(*) from incident_ i
        left join reservation_ r on r.id_ = i.reservation_id_ and r.cell_id_ = i.cell_id_
            and r.order_id_ = i.order_id_
        left join lockermat_cell_ c on c.id_ = i.cell_id_
        where c.id_ is null or (i.reservation_id_ is null) != (i.order_id_ is null)
           or (i.reservation_id_ is not null and r.id_ is null)
           or (i.source_ = 'CUSTOMER' and i.reservation_id_ is null)
           or (i.source_ in ('CUSTOMER', 'TERMINAL')) != (i.reported_by_keycloak_id_ is null)
           or (i.status_ in ('RESOLVED', 'REJECTED')) != (i.resolved_at_ is not null)
           or (i.resolved_at_ is not null and (
               i.resolution_ is null or i.resolved_by_keycloak_id_ is null or i.resolved_at_ < i.created_at_
           ))
    """,
}
SLICE_QUERIES = {
    "unreferenced customers": """
        select count(*) from customer_ c where not exists (select 1 from order_ o where o.customer_id_ = c.id_)
    """,
    "unused lockers": """
        select count(*) from lockermat_ l where not exists (
            select 1 from lockermat_cell_ c left join reservation_ r on r.cell_id_ = c.id_
            left join incident_ i on i.cell_id_ = c.id_
            where c.lockermat_id_ = l.id_ and (r.id_ is not null or i.id_ is not null)
        )
    """,
    "overdue occupied legs": """
        select count(*) from reservation_ where status_ = 'OCCUPIED' and to_ < getvariable('benchmark_t0')
    """,
    "unpaid orders past deadline": """
        select count(*) from order_ where status_ = 'AWAITING_PAYMENT' and payment_deadline_ < getvariable('benchmark_t0')
    """,
    "expired active codes": """
        select count(*) from access_code_ where status_ = 'ACTIVE' and valid_to_ < getvariable('benchmark_t0')
    """,
    "pending openings": "select count(*) from cell_opening_ where result_ = 'PENDING'",
}
PAID_TARGET = {"XS": 100, "S": 5000, "M": 5000, "L": 5000}


def check_ledger(db, profile, plan, check_constraints=True):
    db.execute("set variable benchmark_t0 = ?", [profile.t0])
    if check_constraints:
        check_bookings(db, profile, plan)
        require_empty(db, CHECKS)
    for name in TABLES:
        actual = db.execute(f"select count(*) from {name}").fetchone()[0]
        if actual != plan.counts[name]:
            raise ValueError(f"{name}: expected {plan.counts[name]} rows, found {actual}")
    failed, old = db.execute("""
        select count(*) filter (where result_ = 'DOOR_FAILED'),
            count(*) filter (where requested_at_ < getvariable('benchmark_t0') - interval '540 days')
        from cell_opening_
    """).fetchone()
    if failed != plan.failed_openings or failed / plan.counts["cell_opening_"] > 0.15:
        raise ValueError(f"Unexpected door failure count: {failed}")
    if not old:
        raise ValueError("No old door journal rows")
    paid = db.execute("select count(*) from order_ where status_ = 'PAID'").fetchone()[0]
    if paid < PAID_TARGET[profile.size]:
        raise ValueError(f"Expected at least {PAID_TARGET[profile.size]} paid orders, found {paid}")
    for name, expected in exact_slices(profile, plan).items():
        found = db.execute(SLICE_QUERIES[name]).fetchone()[0]
        if found != expected:
            raise ValueError(f"{name}: expected {expected}, found {found}")
        print(f"{profile.size} {name}: {found:,}")
    print(f"{profile.size}: {paid:,} PAID candidates, {old:,} old journal rows, {failed:,} door failures")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("XS", "S", "M", "L"), required=True)
    parser.add_argument("--slices-only", action="store_true")
    args = parser.parse_args()
    profile = load_profile(args.size)
    with connect(profile.destination, TABLES) as db:
        check_ledger(db, profile, make_plan(profile), not args.slices_only)


if __name__ == "__main__":
    main()
