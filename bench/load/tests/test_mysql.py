import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from bench.load.mysql.loader import transformer, write_csv

CODES = [("id_", "bigint", None), ("code_hmac_", "binary", 32), ("sent_to_phone_", "varchar", 16), ("valid_from_", "datetime", None)]
EVENTS = [("id_", "bigint", None), ("changes_", "json", None), ("changes_new_", "json", None)]
VALID_FROM = datetime(2026, 10, 31, 0, 15, 0, 123000, tzinfo=timezone.utc)


class MysqlTransformTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.directory = Path(self.scratch.name)
        self.parquet = transformer()

    def tearDown(self):
        self.parquet.close()
        self.scratch.cleanup()

    def convert(self, table, columns, rows):
        path = self.directory / f"{table}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        target = self.directory / f"{table}.csv"
        write_csv(self.parquet, path, columns, target)
        return target.read_text().splitlines()

    def test_digest_length(self):
        row = {"id_": 1, "code_hmac_": b"\xab" * 31, "sent_to_phone_": None, "valid_from_": VALID_FROM}
        with self.assertRaisesRegex(ValueError, "access_code_.code_hmac_: 1 values are not 32 bytes long"):
            self.convert("access_code_", CODES, [row])
        row["code_hmac_"] = b"\xab" * 32
        expected = f'"1","{"AB" * 32}",NULL,"2026-10-31 00:15:00.123"'
        self.assertEqual(self.convert("access_code_", CODES, [row]), [expected])

    def test_changes_new(self):
        changes = '[{"f": "status_", "old": "PAID", "new": "CANCELLED"}, {"f": "closed_at_", "old": null, "new": null}]'
        rows = [{"id_": 1, "changes_": changes}, {"id_": 2, "changes_": "[]"}, {"id_": 3, "changes_": None}]
        self.assertEqual(self.convert("audit_event_", EVENTS, rows),
                         [f'"1","{changes.replace('"', '""')}","[""CANCELLED""]"', '"2","[]","[]"', '"3",NULL,NULL'])


if __name__ == "__main__":
    unittest.main()
