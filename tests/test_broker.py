import unittest

import pandas as pd

from quant_platform.backtest.broker import BacktestBroker


class BacktestBrokerAccountingTests(unittest.TestCase):
    def _frame(self, opens, closes):
        index = pd.date_range("2026-01-01", periods=len(opens), freq="1h", tz="UTC")
        return pd.DataFrame(
            {
                "open": opens,
                "high": [max(o, c) for o, c in zip(opens, closes)],
                "low": [min(o, c) for o, c in zip(opens, closes)],
                "close": closes,
                "volume": 1.0,
            },
            index=index,
        )

    def test_new_position_does_not_receive_pre_fill_gap(self):
        df = self._frame([100.0, 200.0, 200.0], [100.0, 200.0, 200.0])
        signal = pd.Series([1.0, 1.0, 1.0], index=df.index)

        result = BacktestBroker(0.0, 0.0).run(df, signal)

        self.assertEqual(result.fills[0].price, 200.0)
        self.assertAlmostEqual(result.returns.iloc[1], 0.0)

    def test_existing_position_receives_overnight_gap(self):
        df = self._frame([100.0, 100.0, 200.0], [100.0, 100.0, 200.0])
        signal = pd.Series([1.0, 1.0, 1.0], index=df.index)

        result = BacktestBroker(0.0, 0.0).run(df, signal)

        self.assertAlmostEqual(result.returns.iloc[2], 1.0)

    def test_exit_at_open_avoids_following_intraday_move(self):
        df = self._frame([100.0, 100.0, 100.0], [100.0, 100.0, 200.0])
        signal = pd.Series([1.0, 0.0, 0.0], index=df.index)

        result = BacktestBroker(0.0, 0.0).run(df, signal)

        self.assertEqual(result.position.iloc[2], 0.0)
        self.assertAlmostEqual(result.returns.iloc[2], 0.0)


if __name__ == "__main__":
    unittest.main()
