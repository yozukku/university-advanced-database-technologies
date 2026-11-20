import unittest

from bench.gen.cities import ANCHORS, POLAND_BOX
from bench.gen.plan import make_plan
from bench.gen.profiles import load_profile
from bench.gen.static import WKB_POINT, static_tables


REFERENCE = {
    "S": (125, 5000, 612, 9, 5771, 46170, 55404, 9234, 99266, 87727, 50787, 1385, 138510),
    "M": (250, 10000, 1225, 9, 11543, 92342, 110810, 18468, 198535, 175446, 101576, 2770, 277026),
    "L": (2500, 100000, 12250, 9, 115428, 923423, 1108108, 184685, 1985359, 1754501, 1015765, 27703, 2770269),
}
TABLES = (
    "lockermat_", "lockermat_cell_", "lockermat_opening_hours_", "tariff_", "customer_", "order_",
    "reservation_", "shipment_", "access_code_", "cell_opening_", "payment_", "incident_", "audit_event_",
)


class PlannerTest(unittest.TestCase):
    def test_exact_totals_and_lifecycle_mix(self):
        for size, expected in REFERENCE.items():
            with self.subTest(size=size):
                profile = load_profile(size)
                plan = make_plan(profile)
                self.assertEqual(set(plan.counts), set(TABLES))
                self.assertEqual(sum(plan.counts.values()), profile.records)
                for index, (table, reference) in enumerate(zip(TABLES, expected)):
                    actual = plan.counts[table]
                    if index < 4:
                        self.assertEqual(actual, reference)
                    else:
                        self.assertLessEqual(abs(actual - reference), reference * 0.10, table)
                self.assertLessEqual(2.5, plan.events_per_order)
                self.assertLessEqual(plan.events_per_order, 3.5)
                self.assertLessEqual(plan.failed_openings / plan.counts["cell_opening_"], 0.15)
                self.assertGreater(plan.closed_older_orders, plan.older_orders / 2)

    def test_statics_include_anchors_and_poland_box(self):
        for size in ("XS", "S", "M", "L"):
            with self.subTest(size=size):
                profile = load_profile(size)
                plan = make_plan(profile)
                tables = dict(static_tables(profile, plan))
                for name, table in tables.items():
                    self.assertEqual(table.num_rows, plan.counts[name])
                west, east, south, north = POLAND_BOX
                for row in tables["lockermat_"].to_pylist():
                    _, _, srid, lng, lat = WKB_POINT.unpack(row["location_"])
                    self.assertEqual(srid, 4326)
                    self.assertTrue(west <= lng <= east and south <= lat <= north)
                actual = [
                    (row["name_"], *WKB_POINT.unpack(row["location_"])[-2:])
                    for row in tables["lockermat_"].slice(0, 2).to_pylist()
                ]
                self.assertEqual(actual, list(ANCHORS))
