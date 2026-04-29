import tempfile
import unittest
from pathlib import Path

from app.models import AnalyzeRequest
from app.services import TrendTraderService


class RepositoryFlowTest(unittest.TestCase):
    def test_plan_sync_and_tick_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            analysis = service.analyze(AnalyzeRequest(symbol="000001", strategy_name="trend_trading"))
            self.assertIsNotNone(analysis.trade_plan)

            synced = service.repository.sync_watchlist_from_plans()
            self.assertGreaterEqual(synced, 0)

            if analysis.trade_plan and analysis.trade_plan.entry_price:
                alerts = service.repository.evaluate_tick("000001", analysis.trade_plan.entry_price * 1.01)
                self.assertLessEqual(len(alerts), 1)


if __name__ == "__main__":
    unittest.main()
