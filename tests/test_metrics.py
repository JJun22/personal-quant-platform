import unittest

import numpy as np
import pandas as pd

from quant_platform.backtest.metrics import sharpe_p_value


class SharpeEvidenceTests(unittest.TestCase):
    def test_positive_signal_has_small_null_p_value(self):
        rng = np.random.default_rng(7)
        returns = pd.Series(rng.normal(0.002, 0.01, 1500))
        self.assertLess(sharpe_p_value(returns, 86400, n_boot=500), 0.05)

    def test_negative_observed_sharpe_does_not_reject_null(self):
        returns = pd.Series([-0.01, 0.0, -0.02, 0.005] * 100)
        self.assertEqual(sharpe_p_value(returns, 86400, n_boot=200), 1.0)


if __name__ == "__main__":
    unittest.main()
