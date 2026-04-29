import unittest

from app.data.providers import SampleDailyBarProvider
from app.strategies.trend_trading import TrendTradingStrategy


class TrendTradingStrategyTest(unittest.TestCase):
    def test_analysis_contains_core_outputs(self):
        bars = SampleDailyBarProvider().fetch_daily_bars("000001")
        analysis = TrendTradingStrategy().analyze("000001", bars)

        self.assertEqual(analysis.symbol, "000001")
        self.assertEqual(analysis.strategy_name, "trend_trading")
        self.assertGreater(len(analysis.bars), 200)
        self.assertGreaterEqual(analysis.score, 0)
        self.assertLessEqual(analysis.score, 100)
        self.assertIn("structure", analysis.score_breakdown)
        self.assertIn("volume_ratio_20d", analysis.metrics)
        self.assertIsNotNone(analysis.trade_plan)
        self.assertGreater(len(analysis.overlays), 0)

    def test_short_history_returns_no_setup(self):
        bars = SampleDailyBarProvider().fetch_daily_bars("000001")[:20]
        analysis = TrendTradingStrategy().analyze("000001", bars)
        self.assertEqual(analysis.status, "no_setup")
        self.assertEqual(analysis.score, 0)


if __name__ == "__main__":
    unittest.main()
