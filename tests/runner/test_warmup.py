from dataclasses import dataclass

import pytest

from bench.runner.warmup import Index, listing, script

TEXT = {
    "pg": "select * from shipment_ s join reservation_ r on r.order_id_ = s.order_id_",
    "mysql": "select * from shipment_ s join reservation_ r on r.order_id_ = s.order_id_",
    "mongo": "orders.aggregate([...]); lockermats.find(...)",
    "neo4j": "MATCH (o:Shipment)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(c:Cell) RETURN o",
}
BASE = {
    "pg": {("table", "shipment_"): [Index("shipment__pkey", "btree")], ("table", "reservation_"): [Index("reservation__pkey", "btree")],
           ("table", "customer_"): [Index("customer__pkey", "btree")]},
    "mysql": {("table", "shipment_"): [Index("PRIMARY", "btree")], ("table", "audit_event_"): [Index("PRIMARY", "btree")],
              ("table", "reservation_"): [Index("PRIMARY", "btree"), Index("reservation_cell__fk", "btree")]},
    "mongo": {("collection", "orders"): [Index("_id_", "btree", (("_id", 1),))],
              ("collection", "lockermats"): [Index("_id_", "btree", (("_id", 1),)),
                                             Index("location_2dsphere", "2dsphere", (("location", "2dsphere"),))]},
    "neo4j": {("node", "Shipment"): [Index("Shipment_id__uq", "range", ("shipmentId",))], ("node", "Reservation"): [],
              ("node", "Cell"): [Index("Cell_id__uq", "range", ("id",))], ("relationship", "HAS_LEG"): [],
              ("relationship", "IN_CELL"): [], ("node", "Customer"): []},
}
ADDED = {
    "pg": ("shipment_", Index("ix1__idx", "btree")),
    "mysql": ("shipment_", Index("ix1__idx", "btree")),
    "mongo": ("orders", Index("ix1__idx", "btree", (("shipment.recipientPhone", 1),), '{"shipment.recipientPhone": {"$exists": true}}')),
    "neo4j": ("Shipment", Index("ix1__idx", "range", ("recipientPhone",))),
}


@dataclass
class Impl:
    text: str


@dataclass
class Reading:
    impls: dict


def idx(engine):
    scope, index = ADDED[engine]
    found = {key: list(indexes) for key, indexes in BASE[engine].items()}
    key = next(key for key in found if key[1] == scope)
    found[key].append(index)
    return found


@pytest.mark.parametrize("engine", ("pg", "mysql", "mongo", "neo4j"))
def test_the_script_differs_only_by_the_idx_catalog(engine):
    scenario = Reading({engine: Impl(TEXT[engine])})
    base = listing(script(engine, BASE[engine], [scenario], ["CANCELLED", "PAID"]))
    steps = script(engine, idx(engine), [scenario], ["CANCELLED", "PAID"])
    extended = listing(steps)
    assert [text for text in extended if text in base] == base
    assert [step.index for step, text in zip(steps, extended) if text not in base] == ["ix1__idx"]
    assert not any("customer" in text.lower() or "audit_event_" in text for text in extended)


def test_mysql_warms_a_multi_valued_index_by_value_batches():
    found = {("table", "audit_event_"): [Index("PRIMARY", "btree"), Index("jx2__idx", "multi_valued", ("changes_new_",)),
                                         Index("lockermat_location__idx", "spatial")]}
    steps = script("mysql", found, [Reading({"mysql": Impl("select * from audit_event_")})], [str(n) for n in range(2500)])
    assert [step.index for step in steps] == ["PRIMARY", "jx2__idx", "jx2__idx", "jx2__idx", "lockermat_location__idx"]
    assert steps[1].text.endswith("where json_overlaps(changes_new_, cast(%s as json))") and steps[-1].text == ""
