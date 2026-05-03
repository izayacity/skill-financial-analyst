import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from persist.persist_factory import PersistFactory


class TestPersistFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_read_from_local_parquet_file(self) -> None:
        parquet_path = self.base_path / "sample_read.parquet"
        expected_df = pd.DataFrame(
            [
                {"id": 1, "name": "Alice", "score": 91.5},
                {"id": 2, "name": "Bob", "score": 88.0},
            ]
        )
        expected_df.to_parquet(parquet_path, engine="pyarrow", index=False)

        factory = PersistFactory("parquet", str(parquet_path))
        actual_df = factory.read()

        self.assertIsInstance(actual_df, pd.DataFrame)
        pd.testing.assert_frame_equal(actual_df.reset_index(drop=True), expected_df.reset_index(drop=True))

    def test_write_to_local_parquet_file(self) -> None:
        parquet_path = self.base_path / "sample_write.parquet"
        input_df = pd.DataFrame(
            [
                {"id": 10, "symbol": "AAPL", "price": 180.25},
                {"id": 11, "symbol": "MSFT", "price": 405.30},
            ]
        )

        factory = PersistFactory("parquet", str(parquet_path))
        factory.write(input_df, append=False)

        self.assertTrue(parquet_path.exists())
        actual_df = pd.read_parquet(parquet_path, engine="pyarrow")
        pd.testing.assert_frame_equal(actual_df.reset_index(drop=True), input_df.reset_index(drop=True))

    def test_read_from_local_jsonl_file(self) -> None:
        jsonl_path = self.base_path / "sample_read.jsonl"
        expected_rows = [
            {"id": 1, "event": "login", "ok": True},
            {"id": 2, "event": "trade", "ok": False},
        ]
        with open(jsonl_path, "w", encoding="utf-8") as handle:
            for row in expected_rows:
                handle.write(json.dumps(row) + "\n")

        factory = PersistFactory("jsonl", str(jsonl_path))
        actual_rows = factory.read()

        self.assertIsInstance(actual_rows, list)
        self.assertEqual(actual_rows, expected_rows)

    def test_write_to_local_jsonl_file(self) -> None:
        jsonl_path = self.base_path / "sample_write.jsonl"
        input_rows = [
            {"id": 100, "ticker": "NVDA", "side": "BUY"},
            {"id": 101, "ticker": "TSLA", "side": "SELL"},
        ]

        factory = PersistFactory("jsonl", str(jsonl_path))
        factory.write(input_rows, append=False)

        self.assertTrue(jsonl_path.exists())
        with open(jsonl_path, "r", encoding="utf-8") as handle:
            actual_rows = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(actual_rows, input_rows)


if __name__ == "__main__":
    unittest.main()
