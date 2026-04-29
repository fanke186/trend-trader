import tempfile
import unittest
from pathlib import Path

from app.agent.tool_loop import AgentToolLoop
from app.models import AnalyzeRequest, StrategySpec, WorkflowScript
from app.monitoring.condition_evaluator import ConditionEvaluator
from app.services import TrendTraderService
from app.strategies.interpreter import StrategyInterpreter


class PhasePlanFeaturesTest(unittest.TestCase):
    def test_crosses_above_uses_previous_value(self):
        evaluator = ConditionEvaluator()
        condition = {"op": "crosses_above", "left": {"var": "last_price"}, "right": 18.3}

        self.assertFalse(evaluator.evaluate(condition, {"symbol": "002261", "last_price": 18.0}))
        evaluator.update_context({"symbol": "002261", "last_price": 18.0})

        self.assertTrue(evaluator.evaluate(condition, {"symbol": "002261", "last_price": 18.5}))
        evaluator.update_context({"symbol": "002261", "last_price": 18.5})

        self.assertFalse(evaluator.evaluate(condition, {"symbol": "002261", "last_price": 18.7}))

    def test_tool_loop_invokes_registry_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            loop = AgentToolLoop(service.tools)
            calls = {"count": 0}

            def llm_caller(messages, tools):
                calls["count"] += 1
                if calls["count"] == 1:
                    return {
                        "choices": [
                            {
                                "finish_reason": "tool_calls",
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "strategy.analyze",
                                                "arguments": '{"symbol":"000001","strategy_name":"trend_trading"}',
                                            },
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "done"}}]}

            result = loop.run(
                {"system_prompt": "test", "tools_allowed": ["strategy.analyze"], "max_turns": 4},
                "analyze",
                {},
                llm_caller,
            )

            self.assertEqual(result["text"], "done")
            self.assertEqual(result["tool_calls"][0]["tool"], "strategy.analyze")

    def test_validate_workflow_rejects_missing_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            workflow = WorkflowScript(version=1, steps=[{"type": "agent", "arguments": {"agent_id": 999999, "prompt": "x"}}])

            with self.assertRaises(KeyError):
                service.validate_workflow(workflow)

    def test_strategy_engine_and_interpreter_are_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TrendTraderService(Path(tmp))
            analysis = service.analyze(AnalyzeRequest(symbol="000001", strategy_name="trend_trading"))
            self.assertEqual(analysis.strategy_name, "trend_trading")
            self.assertGreaterEqual(len(analysis.bars), 40)

            spec = StrategySpec(
                name="stable",
                description="稳定释义测试",
                features=[{"name": "volume_ratio_20d", "params": {"period": 20}}],
                scoring=[{"name": "volume", "weight": 100}],
            )
            interpreter = StrategyInterpreter()
            self.assertEqual(interpreter.explain(spec), interpreter.explain(spec))


if __name__ == "__main__":
    unittest.main()
