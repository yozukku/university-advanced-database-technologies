from dataclasses import dataclass


ORDER_RECORDS = 10.705


@dataclass(frozen=True)
class Cohort:
    name: str
    weight: int
    status: str
    legs: tuple[str, ...]
    paid: bool

    @property
    def shipment(self):
        return len(self.legs) == 2

    @property
    def refund(self):
        return self.paid and self.status == "CANCELLED"

    @property
    def closed(self):
        return self.status in {"COMPLETED", "CANCELLED", "EXPIRED"}

    @property
    def audit_events(self):
        terminal = self.status in {"CANCELLED", "EXPIRED"}
        movements = sum((state == "OCCUPIED") + 2 * (state == "COMPLETED") for state in self.legs)
        return 1 + self.paid + terminal + self.refund + movements


COHORTS = (
    Cohort("storage_awaiting", 5000, "AWAITING_PAYMENT", ("BOOKED",), False),
    Cohort("storage_expired", 13750, "EXPIRED", ("CANCELLED",), False),
    Cohort("storage_booked", 59000, "PAID", ("BOOKED",), True),
    Cohort("storage_occupied", 12000, "PAID", ("OCCUPIED",), True),
    Cohort("storage_completed", 55000, "COMPLETED", ("COMPLETED",), True),
    Cohort("storage_cancelled", 15250, "CANCELLED", ("CANCELLED",), True),
    Cohort("shipment_awaiting", 800, "AWAITING_PAYMENT", ("BOOKED", "BOOKED"), False),
    Cohort("shipment_expired", 2325, "EXPIRED", ("CANCELLED", "CANCELLED"), False),
    Cohort("shipment_booked", 10000, "PAID", ("BOOKED", "BOOKED"), True),
    Cohort("shipment_in_transit", 3600, "PAID", ("COMPLETED", "BOOKED"), True),
    Cohort("shipment_occupied", 3400, "PAID", ("COMPLETED", "OCCUPIED"), True),
    Cohort("shipment_completed", 15125, "COMPLETED", ("COMPLETED", "COMPLETED"), True),
    Cohort("shipment_cancelled", 4750, "CANCELLED", ("CANCELLED", "CANCELLED"), True),
)


@dataclass(frozen=True)
class DatasetPlan:
    counts: dict[str, int]
    cohorts: tuple[tuple[Cohort, int], ...]
    failed_openings: int

    @property
    def events_per_order(self):
        return self.counts["audit_event_"] / self.counts["order_"]

    @property
    def closed_older_orders(self):
        return sum(count * 3 // 4 for cohort, count in self.cohorts if cohort.closed)

    @property
    def older_orders(self):
        return self.closed_older_orders + sum(count // 100 for cohort, count in self.cohorts if not cohort.closed)


def make_plan(profile):
    lockers = max(2, profile.records // 4000)
    static = {
        "lockermat_": lockers,
        "lockermat_cell_": 40 * lockers,
        "lockermat_opening_hours_": round(4.9 * lockers),
        "tariff_": 9,
    }
    orders = round((profile.records - sum(static.values())) / ORDER_RECORDS)
    cohorts = allocate_cohorts(orders)
    shipments = sum(count for cohort, count in cohorts if cohort.shipment)
    counts = {
        **static,
        "customer_": round(orders / 8),
        "order_": orders,
        "reservation_": orders + shipments,
        "shipment_": shipments,
        "access_code_": sum(2 * len(cohort.legs) * count for cohort, count in cohorts if cohort.paid),
        "payment_": orders + sum(count for cohort, count in cohorts if cohort.refund),
        "incident_": round(orders * 0.03),
        "audit_event_": sum(cohort.audit_events * count for cohort, count in cohorts),
    }
    openings = profile.records - sum(counts.values())
    counts["cell_opening_"] = openings
    return DatasetPlan(counts, cohorts, openings // 10)


def allocate_cohorts(orders):
    total_weight = sum(cohort.weight for cohort in COHORTS)
    allocations = [divmod(orders * cohort.weight, total_weight) for cohort in COHORTS]
    counts = [quotient for quotient, _ in allocations]
    remainder = orders - sum(counts)
    by_remainder = sorted(range(len(counts)), key=lambda index: allocations[index][1], reverse=True)
    for index in by_remainder[:remainder]:
        counts[index] += 1
    return tuple(zip(COHORTS, counts))
