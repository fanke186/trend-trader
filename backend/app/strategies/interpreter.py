from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Optional

from app.models import StrategySpec

LLMCaller = Callable[[list[dict[str, Any]], Optional[list[dict[str, Any]]]], dict[str, Any]]


class StrategyInterpreter:
    """Stable natural-language StrategySpec interpreter."""

    def __init__(self, llm_caller: LLMCaller | None = None) -> None:
        self._llm = llm_caller
        self._cache: dict[str, str] = {}

    def explain(self, spec: StrategySpec) -> str:
        spec_hash = self.hash_spec(spec)
        if spec_hash in self._cache:
            return self._cache[spec_hash]
        if self._llm:
            text = self._explain_with_llm(spec)
        else:
            text = self._deterministic_explanation(spec)
        self._cache[spec_hash] = text
        return text

    def hash_spec(self, spec: StrategySpec) -> str:
        data = json.dumps(
            {
                "features": spec.features,
                "filters": spec.filters,
                "scoring": spec.scoring,
                "overlays": spec.overlays,
                "trade_plan_template": spec.trade_plan_template,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

    def _explain_with_llm(self, spec: StrategySpec) -> str:
        response = self._llm(
            [
                {"role": "system", "content": "你是量化策略分析师。用中文稳定、结构化解释策略，不添加收益承诺。"},
                {"role": "user", "content": self._prompt(spec)},
            ],
            None,
        )
        choices = response.get("choices") or []
        if choices:
            return str((choices[0].get("message") or {}).get("content") or "").strip()
        return self._deterministic_explanation(spec)

    def _deterministic_explanation(self, spec: StrategySpec) -> str:
        feature_lines = "\n".join(f"- {item.get('name')}: 参数 {json.dumps(item.get('params') or {}, ensure_ascii=False)}" for item in spec.features) or "- 无"
        filter_lines = "\n".join(f"- {item.get('op') or item.get('name')}: 参数 {json.dumps(item.get('params') or {}, ensure_ascii=False)}" for item in spec.filters) or "- 无"
        score_lines = "\n".join(f"- {item.get('name')}: 权重 {item.get('weight', 0)}" for item in spec.scoring) or "- 无"
        return (
            "## 策略概述\n"
            f"{spec.description or spec.name}。\n\n"
            "## 特征计算\n"
            f"{feature_lines}\n\n"
            "## 筛选条件\n"
            f"{filter_lines}\n\n"
            "## 评分体系\n"
            f"{score_lines}\n\n"
            "## 交易计划生成\n"
            f"根据模板生成入场、止损、止盈和失效条件：{json.dumps(spec.trade_plan_template or {}, ensure_ascii=False)}"
        )

    def _prompt(self, spec: StrategySpec) -> str:
        return f"""
策略名称: {spec.name}
策略描述: {spec.description}

features:
{json.dumps(spec.features, ensure_ascii=False, indent=2)}

filters:
{json.dumps(spec.filters, ensure_ascii=False, indent=2)}

scoring:
{json.dumps(spec.scoring, ensure_ascii=False, indent=2)}

overlays:
{json.dumps(spec.overlays, ensure_ascii=False, indent=2)}

trade_plan_template:
{json.dumps(spec.trade_plan_template, ensure_ascii=False, indent=2)}

请按以下结构输出:
## 策略概述
## 特征计算
## 筛选条件
## 评分体系
## 交易计划生成
"""
