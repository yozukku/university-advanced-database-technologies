import json
import unittest
from pathlib import Path

from bson import json_util
from bson.int64 import Int64
from bson.json_util import CANONICAL_JSON_OPTIONS
from pymongo.errors import WriteError

from bench.load.mongo.loader import DDL, apply_index, connect, import_collection, run_script
from bench.transform.mongo.transform import transform

DATA = Path("out/xs/data")
GOLDEN = Path("bench/load/tests/golden")
DATABASE = "ddl_rules_"
ORDER = 17
EVENT = 17
DOCUMENT_VALIDATION_FAILURE = 121


def canonical(document):
    return json.loads(json_util.dumps(document, json_options=CANONICAL_JSON_OPTIONS))


class MongoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = connect()
        cls.client.drop_database(DATABASE)
        cls.db = cls.client[DATABASE]
        run_script(cls.db, "base/collections.json")
        transform(DATA, DATA / "mongo")
        for collection in ("orders", "auditEvents"):
            import_collection(DATABASE, collection, DATA / "mongo" / f"{collection}.json")

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database(DATABASE)
        cls.client.close()

    def assert_golden(self, collection, identifier, name):
        expected = json.loads((GOLDEN / name).read_text())
        self.assertEqual(canonical(self.db[collection].find_one({"_id": identifier})), expected)

    def test_shipment_order_matches_golden_document(self):
        self.assert_golden("orders", ORDER, "shipment_order.json")

    def test_audit_event_matches_golden_document(self):
        self.assert_golden("auditEvents", EVENT, "audit_event.json")

    def copy_of_order(self):
        return self.db.orders.find_one({"_id": ORDER}) | {"_id": Int64(-ORDER), "number": "BAG-COPY"}

    def assert_rejected(self, document):
        with self.assertRaises(WriteError) as error:
            self.db.orders.insert_one(document)
        self.assertEqual(error.exception.code, DOCUMENT_VALIDATION_FAILURE)

    def test_invalid_status_is_rejected(self):
        self.db.orders.insert_one(self.copy_of_order())
        self.db.orders.delete_one({"_id": Int64(-ORDER)})
        self.assert_rejected(self.copy_of_order() | {"status": "LOST"})
        order = self.copy_of_order()
        order["reservations"][0]["status"] = "LOST"
        self.assert_rejected(order)

    def test_index_scripts_create_without_error(self):
        run_script(self.db, "base/indexes.json")
        apply_index(self.db)
        for name in ("base/indexes.json", "idx/indexes.json"):
            for command in json.loads((DDL / name).read_text()):
                created = {index["name"] for index in self.db[command["createIndexes"]].list_indexes()}
                self.assertLessEqual({index["name"] for index in command["indexes"]}, created)


if __name__ == "__main__":
    unittest.main()
