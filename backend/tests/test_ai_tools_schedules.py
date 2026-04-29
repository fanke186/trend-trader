import tempfile
import unittest
from pathlib import Path

from app.models import ConditionOrder
from app.services import TrendTraderService


class AIToolsSchedulesTest(unittest.TestCase):
    def test_defaults_and_tool_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            providers = service.repository.list_generic("model_providers")
            tools = service.tools.list_definitions()

            self.assertTrue(any(provider["provider_type"] == "glm" for provider in providers))
            self.assertTrue(any(tool.name == "strategy.analyze" for tool in tools))

            blocked = service.tools.invoke(
                "strategy.screener_run",
                {"symbols": ["000001"], "strategy_name": "trend_trading"},
                source="test",
                confirmed=False,
            )
            self.assertEqual(blocked.status, "confirmation_required")

            allowed = service.tools.invoke(
                "strategy.screener_run",
                {"symbols": ["000001"], "strategy_name": "trend_trading"},
                source="test",
                confirmed=True,
            )
            self.assertEqual(allowed.status, "ok")

    def test_condition_order_triggers_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            order = ConditionOrder(
                name="000001 test breakout",
                symbol="000001",
                condition={"op": "gte", "left": {"var": "last_price"}, "right": 10},
            )
            service.repository.save_condition_order(order)

            events = service.evaluate_condition_orders("000001", 10.5)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["category"], "condition_order")
            self.assertEqual(events[0]["status"], "triggered")

    def test_schedule_can_run_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            schedules = service.repository.list_generic("schedules")
            self.assertGreaterEqual(len(schedules), 1)

            run = service.run_schedule(int(schedules[0]["id"]))

            self.assertEqual(run["status"], "ok")
            self.assertIn("output", run)


if __name__ == "__main__":
    unittest.main()
