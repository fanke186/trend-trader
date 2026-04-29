from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Any, Callable

from app.models import ChartOverlay, ChartPoint, DailyBar, StrategyAnalysis, StrategySpec, TradePlan


@dataclass
class Pivot:
    index: int
    price: float
    kind: str


FeatureBuilder = Callable[[list[DailyBar], dict[str, Any]], Any]
ScoringRule = Callable[[dict[str, Any]], float]
FilterRule = Callable[[dict[str, Any], dict[str, Any]], bool]


class StrategyEngine:
    """Generic StrategySpec executor."""

    def __init__(self) -> None:
        self._feature_builders: dict[str, FeatureBuilder] = {
            "pivot_high_low": _build_pivot_features,
            "support_resistance_lines": _build_sr_lines,
            "volume_ratio_20d": _build_volume_ratio,
            "ma_cross": _build_ma_cross,
            "rsi": _build_rsi,
            "macd": _build_macd,
            "breakout": _build_breakout,
            "daily_bars": lambda bars, params: {"count": len(bars), "latest_close": bars[-1].close if bars else 0},
        }
        self._scoring_rules: dict[str, ScoringRule] = {
            "structure": _score_structure,
            "breakout": _score_breakout,
            "volume": _score_volume,
            "risk_reward": _score_risk_reward,
            "trend": _score_trend,
            "momentum": _score_momentum,
            "trend_structure": _score_structure,
            "volume_confirmation": _score_volume,
        }
        self._filter_rules: dict[str, FilterRule] = {
            "manual_review_required": lambda features, params: True,
            "volume_min": _filter_volume_min,
            "price_above_ma": _filter_price_above_ma,
        }

    def execute(self, spec: StrategySpec, bars: list[DailyBar]) -> StrategyAnalysis:
        if len(bars) < 40:
            return self._no_setup(spec, bars, "数据不足 (至少需要 40 根 K 线)")

        features: dict[str, Any] = {"latest_close": bars[-1].close}
        for feature_def in spec.features:
            name = str(feature_def.get("name") or "")
            builder = self._feature_builders.get(name)
            if builder:
                features[name] = builder(bars, dict(feature_def.get("params") or {}))

        self._derive_trade_features(features, bars)

        for filter_def in spec.filters:
            op = str(filter_def.get("op") or filter_def.get("name") or "")
            rule = self._filter_rules.get(op)
            if rule and not rule(features, dict(filter_def.get("params") or {})):
                return self._no_setup(spec, bars, f"不满足筛选条件: {op}")

        score_breakdown: dict[str, float] = {}
        total_score = 0.0
        for score_def in spec.scoring:
            name = str(score_def.get("name") or "")
            weight = float(score_def.get("weight") or 0)
            rule = self._scoring_rules.get(name)
            if rule:
                weighted = rule(features) * weight / 100.0
                score_breakdown[name] = round(weighted, 2)
                total_score += weighted
        total_score = round(min(100.0, max(0.0, total_score)), 2)

        trade_plan = self._build_trade_plan(spec, bars, features, total_score)
        overlays = self._build_overlays(spec, bars, features)
        breakout = bool(features.get("breakout_confirmed") or (isinstance(features.get("breakout"), dict) and features["breakout"].get("confirmed")))
        status = "triggered" if breakout else ("watch" if trade_plan and total_score >= 35 else "no_setup")
        if trade_plan:
            trade_plan.status = status

        return StrategyAnalysis(
            symbol=bars[-1].symbol,
            strategy_name=spec.name,
            as_of=bars[-1].date,
            score=total_score,
            status=status,
            bars=bars,
            score_breakdown=score_breakdown,
            metrics=self._build_metrics(features, bars),
            overlays=overlays,
            trade_plan=trade_plan,
        )

    def _no_setup(self, spec: StrategySpec, bars: list[DailyBar], reason: str) -> StrategyAnalysis:
        as_of = bars[-1].date if bars else date.today()
        return StrategyAnalysis(
            symbol=bars[-1].symbol if bars else "",
            strategy_name=spec.name,
            as_of=as_of,
            score=0,
            status="no_setup",
            bars=bars,
            score_breakdown={},
            metrics={"reason": reason},
            overlays=[],
            trade_plan=None,
        )

    def _derive_trade_features(self, features: dict[str, Any], bars: list[DailyBar]) -> None:
        sr = features.get("support_resistance_lines") if isinstance(features.get("support_resistance_lines"), dict) else {}
        resistance = sr.get("resistance") if isinstance(sr, dict) else None
        support = sr.get("support") if isinstance(sr, dict) else None
        last_idx = len(bars) - 1
        latest = bars[-1]
        if resistance:
            resistance_now = resistance["slope"] * last_idx + resistance["intercept"]
            features["entry_price"] = round(resistance_now * 1.01, 3)
            features["breakout_confirmed"] = latest.close >= resistance_now and latest.volume >= mean([b.volume for b in bars[-20:]]) * 1.1
        if support:
            support_now = support["slope"] * last_idx + support["intercept"]
            features["stop_loss"] = round(support_now * 0.985, 3)
        if features.get("entry_price") and features.get("stop_loss"):
            risk = max(float(features["entry_price"]) - float(features["stop_loss"]), 0.01)
            features["take_profit"] = round(float(features["entry_price"]) + risk * 2.5, 3)
            features["risk_reward_ratio"] = 2.5

    def _build_trade_plan(self, spec: StrategySpec, bars: list[DailyBar], features: dict[str, Any], score: float) -> TradePlan | None:
        template = spec.trade_plan_template or {}
        if not template and not features.get("entry_price"):
            return None
        entry = features.get("entry_price")
        stop = features.get("stop_loss")
        target = features.get("take_profit")
        rr = None
        if entry and stop and float(entry) > float(stop) and target:
            rr = (float(target) - float(entry)) / (float(entry) - float(stop))
        return TradePlan(
            symbol=bars[-1].symbol,
            strategy_name=spec.name,
            status="watch" if score >= 35 else "no_setup",
            entry_price=round(float(entry), 3) if entry else None,
            entry_reason=str(template.get("entry_reason") or "突破关键压力并出现成交确认"),
            stop_loss=round(float(stop), 3) if stop else None,
            take_profit=round(float(target), 3) if target else None,
            risk_reward_ratio=round(rr, 2) if rr else None,
            invalidated_if=str(template.get("invalidated_if") or "跌破止损或结构失效"),
        )

    def _build_overlays(self, spec: StrategySpec, bars: list[DailyBar], features: dict[str, Any]) -> list[ChartOverlay]:
        overlays: list[ChartOverlay] = []
        overlay_defs = spec.overlays or [
            {"kind": "support_line"},
            {"kind": "resistance_line"},
            {"kind": "entry_marker"},
            {"kind": "stop_marker"},
        ]
        sr = features.get("support_resistance_lines") if isinstance(features.get("support_resistance_lines"), dict) else {}
        last_idx = len(bars) - 1
        last_date = bars[-1].date
        for overlay_def in overlay_defs:
            kind = str(overlay_def.get("kind") or "")
            if kind == "support_line" and sr.get("support"):
                line = sr["support"]
                overlays.append(_line_overlay("support", "支撑线", "#00d4aa", bars, line, last_idx, last_date))
            elif kind == "resistance_line" and sr.get("resistance"):
                line = sr["resistance"]
                overlays.append(_line_overlay("resistance", "压力线", "#ff4757", bars, line, last_idx, last_date))
            elif kind == "entry_marker" and features.get("entry_price"):
                overlays.append(_price_overlay("entry", "entry", "买点", "#38bdf8", last_date, float(features["entry_price"])))
            elif kind == "stop_marker" and features.get("stop_loss"):
                overlays.append(_price_overlay("stop", "stop", "止损", "#ff4757", last_date, float(features["stop_loss"])))
        return overlays

    def _build_metrics(self, features: dict[str, Any], bars: list[DailyBar]) -> dict[str, Any]:
        metrics: dict[str, Any] = {"latest_close": bars[-1].close, "bar_count": len(bars)}
        for key, value in features.items():
            if isinstance(value, (int, float, str, bool)):
                metrics[key] = value
            elif isinstance(value, dict):
                for child_key, child_value in value.items():
                    if isinstance(child_value, (int, float, str, bool)):
                        metrics[f"{key}.{child_key}"] = child_value
        return metrics


def _build_pivot_features(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    highs, lows = _find_pivots(bars, int(params.get("window") or 3))
    return {"highs": highs, "lows": lows, "count_high": len(highs), "count_low": len(lows)}


def _build_sr_lines(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    highs, lows = _find_pivots(bars, int(params.get("window") or 3))
    resistance = _line_from_pivots(highs[-5:])
    support = _line_from_pivots(lows[-5:])
    return {
        "resistance": resistance,
        "support": support,
        "resistance_touches": resistance["touches"] if resistance else 0,
        "support_touches": support["touches"] if support else 0,
    }


def _build_volume_ratio(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    period = int(params.get("period") or 20)
    recent = bars[-period:]
    avg = mean([bar.volume for bar in recent]) if recent else 0
    return {"ratio": round(bars[-1].volume / avg, 2) if avg else 0, "latest_volume": bars[-1].volume, "avg_volume": round(avg, 2)}


def _build_ma_cross(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    fast = int(params.get("fast") or 5)
    slow = int(params.get("slow") or 20)
    if len(bars) < slow + 1:
        return {"crossed_up": False, "crossed_down": False, "ma_fast": 0, "ma_slow": 0}
    prev_fast = mean([bar.close for bar in bars[-fast - 1 : -1]])
    prev_slow = mean([bar.close for bar in bars[-slow - 1 : -1]])
    curr_fast = mean([bar.close for bar in bars[-fast:]])
    curr_slow = mean([bar.close for bar in bars[-slow:]])
    return {"ma_fast": round(curr_fast, 3), "ma_slow": round(curr_slow, 3), "crossed_up": prev_fast <= prev_slow and curr_fast > curr_slow, "crossed_down": prev_fast >= prev_slow and curr_fast < curr_slow}


def _build_rsi(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    period = int(params.get("period") or 14)
    if len(bars) < period + 1:
        return {"value": 50}
    gains = 0.0
    losses = 0.0
    for idx in range(-period, 0):
        change = bars[idx].close - bars[idx - 1].close
        if change > 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return {"value": 100}
    rs = (gains / period) / (losses / period)
    return {"value": round(100 - 100 / (1 + rs), 2)}


def _build_macd(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    closes = [bar.close for bar in bars]
    fast = _ema(closes, int(params.get("fast") or 12))
    slow = _ema(closes, int(params.get("slow") or 26))
    macd = fast - slow
    return {"macd": round(macd, 4), "signal": 0, "histogram": round(macd, 4)}


def _build_breakout(bars: list[DailyBar], params: dict[str, Any]) -> dict[str, Any]:
    lookback = int(params.get("lookback") or 20)
    prior_high = max([bar.high for bar in bars[-lookback - 1 : -1]])
    return {"confirmed": bars[-1].close > prior_high, "prior_high": round(prior_high, 3)}


def _score_structure(features: dict[str, Any]) -> float:
    sr = features.get("support_resistance_lines") if isinstance(features.get("support_resistance_lines"), dict) else {}
    return min(100, (50 if sr.get("support_touches", 0) >= 2 else 0) + (50 if sr.get("resistance_touches", 0) >= 2 else 0))


def _score_breakout(features: dict[str, Any]) -> float:
    if features.get("breakout_confirmed"):
        return 100
    sr = features.get("support_resistance_lines") if isinstance(features.get("support_resistance_lines"), dict) else {}
    return 50 if sr.get("resistance") else 0


def _score_volume(features: dict[str, Any]) -> float:
    ratio = (features.get("volume_ratio_20d") or {}).get("ratio", 0) if isinstance(features.get("volume_ratio_20d"), dict) else 0
    return min(100, max(0, (float(ratio) - 0.6) * 60))


def _score_risk_reward(features: dict[str, Any]) -> float:
    return min(100, max(0, float(features.get("risk_reward_ratio") or 0) * 25))


def _score_trend(features: dict[str, Any]) -> float:
    ma = features.get("ma_cross") if isinstance(features.get("ma_cross"), dict) else {}
    if ma.get("crossed_up"):
        return 100
    return 70 if ma.get("ma_fast", 0) > ma.get("ma_slow", 0) else 20


def _score_momentum(features: dict[str, Any]) -> float:
    rsi = (features.get("rsi") or {}).get("value", 50) if isinstance(features.get("rsi"), dict) else 50
    return 80 if 40 <= float(rsi) <= 70 else 40


def _filter_volume_min(features: dict[str, Any], params: dict[str, Any]) -> bool:
    vol = features.get("volume_ratio_20d") if isinstance(features.get("volume_ratio_20d"), dict) else {}
    return float(vol.get("ratio") or 0) >= float(params.get("min_ratio") or 0.8)


def _filter_price_above_ma(features: dict[str, Any], params: dict[str, Any]) -> bool:
    ma = features.get("ma_cross") if isinstance(features.get("ma_cross"), dict) else {}
    return float(features.get("latest_close") or 0) > float(ma.get("ma_slow") or 0)


def _find_pivots(bars: list[DailyBar], window: int) -> tuple[list[Pivot], list[Pivot]]:
    highs: list[Pivot] = []
    lows: list[Pivot] = []
    for idx in range(window, len(bars) - window):
        high_window = [bar.high for bar in bars[idx - window : idx + window + 1]]
        low_window = [bar.low for bar in bars[idx - window : idx + window + 1]]
        if bars[idx].high == max(high_window) and bars[idx].high > max([bar.high for bar in bars[idx - window : idx]]):
            highs.append(Pivot(idx, bars[idx].high, "high"))
        if bars[idx].low == min(low_window) and bars[idx].low < min([bar.low for bar in bars[idx - window : idx]]):
            lows.append(Pivot(idx, bars[idx].low, "low"))
    return highs, lows


def _line_from_pivots(pivots: list[Pivot]) -> dict[str, Any] | None:
    if len(pivots) < 2:
        return None
    p1, p2 = pivots[-2], pivots[-1]
    if p1.index == p2.index:
        return None
    slope = (p2.price - p1.price) / (p2.index - p1.index)
    intercept = p1.price - slope * p1.index
    touches = sum(1 for pivot in pivots if abs(pivot.price - (slope * pivot.index + intercept)) / max(abs(pivot.price), 0.01) < 0.035)
    return {"p1": p1, "p2": p2, "slope": slope, "intercept": intercept, "touches": touches}


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0
    k = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = value * k + result * (1 - k)
    return result


def _line_overlay(id_: str, label: str, color: str, bars: list[DailyBar], line: dict[str, Any], last_idx: int, last_date: date) -> ChartOverlay:
    return ChartOverlay(
        id=id_,
        kind="trend_line",
        name="segment",
        label=label,
        points=[
            ChartPoint(date=bars[line["p1"].index].date, value=round(line["p1"].price, 3)),
            ChartPoint(date=last_date, value=round(line["slope"] * last_idx + line["intercept"], 3)),
        ],
        styles={"line": {"color": color, "size": 2}},
    )


def _price_overlay(id_: str, kind: str, label: str, color: str, at: date, price: float) -> ChartOverlay:
    return ChartOverlay(id=id_, kind=kind, name="priceLine", label=label, points=[ChartPoint(date=at, value=round(price, 3))], styles={"line": {"color": color, "size": 1.5}})
