import sqlite3
import tempfile
import unittest
from pathlib import Path

from quant_platform.data.loader import DatasetRef
from quant_platform.registry import db, repository
from quant_platform.strategy.base import Strategy, StrategyMeta


class FixedStrategy(Strategy):
    def __init__(self, threshold: int, version_label: str = "v1"):
        super().__init__(StrategyMeta("fixed", version_label, {"threshold": threshold}))

    def generate_signals(self, df):
        return df["close"] * 0.0


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "registry.sqlite3"
        db.init_db(self.db_path)
        self.conn = db.get_connection(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_strategy_params_are_part_of_version_identity(self):
        strategy_id = repository.ensure_strategy(self.conn, "fixed")
        first = repository.ensure_strategy_version(self.conn, strategy_id, FixedStrategy(1))
        second = repository.ensure_strategy_version(self.conn, strategy_id, FixedStrategy(2))
        repeated = repository.ensure_strategy_version(self.conn, strategy_id, FixedStrategy(1))

        self.assertNotEqual(first, second)
        self.assertEqual(first, repeated)

    def test_run_summary_uses_column_names(self):
        strategy_id = repository.ensure_strategy(self.conn, "fixed")
        version_id = repository.ensure_strategy_version(self.conn, strategy_id, FixedStrategy(1))
        experiment_id = repository.ensure_experiment(self.conn, "test")
        ref = DatasetRef("BTC/USDT", "1h", Path("data.pkl"), "checksum")
        dataset_id = repository.ensure_dataset(self.conn, ref)
        run_id = repository.start_run(self.conn, experiment_id, version_id, dataset_id, "1h", {})

        summary = repository.get_run_summary(self.conn, run_id)

        self.assertEqual(summary["run_id"], run_id)
        self.assertEqual(summary["strategy_params"], {"threshold": 1})


if __name__ == "__main__":
    unittest.main()
