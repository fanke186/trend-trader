from __future__ import annotations

from typing import Any


class ConditionEvaluator:
    """Condition DSL evaluator with historical cross detection."""

    ALLOWED_OPS = {"all", "any", "not", "gte", "lte", "gt", "lt", "eq", "crosses_above", "crosses_below"}

    def __init__(self) -> None:
        self._previous_values: dict[tuple[str, str], float] = {}

    def evaluate(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        op = str(condition.get("op") or "")
        if op not in self.ALLOWED_OPS:
            raise ValueError(f"unsupported condition operator: {op}")

        if op == "all":
            return all(self.evaluate(dict(item), context) for item in condition.get("conditions", []))
        if op == "any":
            return any(self.evaluate(dict(item), context) for item in condition.get("conditions", []))
        if op == "not":
            return not self.evaluate(dict(condition.get("condition") or {}), context)

        left = self._resolve(condition.get("left"), context)
        right = self._resolve(condition.get("right"), context)
        if op == "gte":
            return left >= right
        if op == "lte":
            return left <= right
        if op == "gt":
            return left > right
        if op == "lt":
            return left < right
        if op == "eq":
            return abs(left - right) < 0.0001
        if op == "crosses_above":
            prev = self._resolve_previous(condition.get("left"), context, left)
            return prev < right <= left
        if op == "crosses_below":
            prev = self._resolve_previous(condition.get("left"), context, left)
            return prev > right >= left
        return False

    def update_context(self, context: dict[str, Any]) -> None:
        symbol = str(context.get("symbol") or "")
        for key, value in context.items():
            if key.startswith("prev_"):
                continue
            if isinstance(value, (int, float)):
                self._previous_values[(symbol, key)] = float(value)

    def _resolve(self, operand: Any, context: dict[str, Any]) -> float:
        if isinstance(operand, dict) and "var" in operand:
            return float(context.get(str(operand["var"]), 0) or 0)
        return float(operand or 0)

    def _resolve_previous(self, operand: Any, context: dict[str, Any], current: float) -> float:
        if not isinstance(operand, dict) or "var" not in operand:
            return current
        var_name = str(operand["var"])
        prev_key = f"prev_{var_name}"
        if prev_key in context:
            return float(context.get(prev_key) or 0)
        symbol = str(context.get("symbol") or "")
        return self._previous_values.get((symbol, var_name), current)
