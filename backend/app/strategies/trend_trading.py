from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.models import ChartOverlay, ChartPoint, DailyBar, StrategyAnalysis, TradePlan
from app.strategies.base import StrategyPlugin


@dataclass(frozen=True)
class Pivot:
    index: int
    price: float
    kind: str


class TrendTradingStrategy(StrategyPlugin):
    name = "trend_trading"

    def analyze(self, symbol: str, bars: list[DailyBar]) -> StrategyAnalysis:
        if len(bars) < 40:
            as_of = bars[-1].date if bars else None
            return StrategyAnalysis(
                symbol=symbol,
                strategy_name=self.name,
                as_of=as_of,
                score=0,
                status="no_setup",
                bars=bars,
                score_breakdown={"data": 0},
                metrics={"reason": "not enough bars"},
                overlays=[],
                trade_plan=None,
            )

        pivots_high = _find_pivots(bars, "high", window=3)
        pivots_low = _find_pivots(bars, "low", window=3)
        resistance = _line_from_pivots(pivots_high[-5:], bars)
        support = _line_from_pivots(pivots_low[-5:], bars)
        key_levels = _key_levels(bars, pivots_high, pivots_low)
        latest = bars[-1]
        previous = bars[-2]

        resistance_now = _line_value(resistance, len(bars) - 1) if resistance else None
        support_now = _line_value(support, len(bars) - 1) if support else None
        avg_volume = mean([bar.volume for bar in bars[-20:]])
        volume_ratio = latest.volume / avg_volume if avg_volume else 0
        breakout = bool(
            resistance_now
            and previous.close <= _line_value(resistance, len(bars) - 2)
            and latest.close > resistance_now
            and volume_ratio >= 1.15
        )

        trend_quality = _trend_quality(support, resistance)
        price_position = _price_position(latest.close, support_now, resistance_now)
        volume_score = min(20, max(0, (volume_ratio - 0.8) * 25))
        breakout_score = 30 if breakout else (14 if resistance_now and latest.close > resistance_now * 0.98 else 4)
        structure_score = min(25, trend_quality)
        risk_score = 0

        entry = resistance_now * 1.005 if resistance_now else None
        stop = support_now * 0.985 if support_now else (min(bar.low for bar in bars[-20:]) if bars else None)
        target = None
        risk_reward = None
        if entry and stop and entry > stop:
            recent_range = max(bar.high for bar in bars[-60:]) - min(bar.low for bar in bars[-60:])
            target = entry + max(recent_range * 0.45, entry - stop * 1.8)
            risk_reward = (target - entry) / (entry - stop) if entry > stop else None
            risk_score = min(25, max(0, (risk_reward or 0) * 8))

        score_breakdown = {
            "structure": round(structure_score, 2),
            "breakout": round(breakout_score, 2),
            "volume": round(volume_score, 2),
            "risk_reward": round(risk_score, 2),
        }
        score = round(min(100, sum(score_breakdown.values())), 2)
        has_actionable_plan = bool(entry and stop and target and structure_score >= 15)
        status = "triggered" if breakout else ("watch" if has_actionable_plan and score >= 35 else "no_setup")

        overlays = _build_overlays(bars, support, resistance, key_levels, entry, stop, target)
        trade_plan = TradePlan(
            symbol=symbol,
            strategy_name=self.name,
            status=status,
            entry_price=round(entry, 3) if entry else None,
            entry_reason="close breaks above descending resistance with volume expansion" if resistance else "waiting for valid resistance line",
            stop_loss=round(stop, 3) if stop else None,
            take_profit=round(target, 3) if target else None,
            risk_reward_ratio=round(risk_reward, 2) if risk_reward else None,
            invalidated_if="daily close falls below support line or recent pivot low",
        )

        metrics = {
            "latest_close": latest.close,
            "volume_ratio_20d": round(volume_ratio, 2),
            "pivot_high_count": len(pivots_high),
            "pivot_low_count": len(pivots_low),
            "resistance_now": round(resistance_now, 3) if resistance_now else None,
            "support_now": round(support_now, 3) if support_now else None,
            "price_position": price_position,
            "breakout_confirmed": breakout,
        }

        return StrategyAnalysis(
            symbol=symbol,
            strategy_name=self.name,
            as_of=latest.date,
            score=score,
            status=status,
            bars=bars,
            score_breakdown=score_breakdown,
            metrics=metrics,
            overlays=overlays,
            trade_plan=trade_plan,
        )


def _find_pivots(bars: list[DailyBar], field: str, window: int) -> list[Pivot]:
    pivots: list[Pivot] = []
    values = [getattr(bar, field) for bar in bars]
    for i in range(window, len(values) - window):
        current = values[i]
        left = values[i - window:i]
        right = values[i + 1:i + 1 + window]
        if field == "high" and current == max(left + [current] + right) and current > max(left) and current >= max(right):
            pivots.append(Pivot(i, current, "high"))
        if field == "low" and current == min(left + [current] + right) and current < min(left) and current <= min(right):
            pivots.append(Pivot(i, current, "low"))
    return pivots


def _line_from_pivots(pivots: list[Pivot], bars: list[DailyBar]) -> dict | None:
    if len(pivots) < 2:
        return None
    p1, p2 = pivots[-2], pivots[-1]
    if p1.index == p2.index:
        return None
    slope = (p2.price - p1.price) / (p2.index - p1.index)
    intercept = p1.price - slope * p1.index
    touches = 0
    for pivot in pivots:
        expected = slope * pivot.index + intercept
        if abs(pivot.price - expected) / max(pivot.price, 0.01) < 0.035:
            touches += 1
    return {"p1": p1, "p2": p2, "slope": slope, "intercept": intercept, "touches": touches}


def _line_value(line: dict, index: int) -> float:
    return line["slope"] * index + line["intercept"]


def _key_levels(bars: list[DailyBar], highs: list[Pivot], lows: list[Pivot]) -> list[dict]:
    levels: list[dict] = []
    for pivot in highs[-3:]:
        levels.append({"kind": "resistance", "price": pivot.price, "index": pivot.index})
    for pivot in lows[-3:]:
        levels.append({"kind": "support", "price": pivot.price, "index": pivot.index})
    high_volume_bars = sorted(bars[-80:], key=lambda bar: bar.volume, reverse=True)[:2]
    for bar in high_volume_bars:
        levels.append({"kind": "volume_level", "price": bar.close, "index": bars.index(bar)})
    return levels


def _trend_quality(support: dict | None, resistance: dict | None) -> float:
    score = 0.0
    if support:
        score += min(12.5, support["touches"] * 4)
        if support["slope"] > 0:
            score += 6
    if resistance:
        score += min(12.5, resistance["touches"] * 4)
        if resistance["slope"] <= 0:
            score += 6
    return min(25, score)


def _price_position(close: float, support: float | None, resistance: float | None) -> str:
    if support and close < support:
        return "below_support"
    if resistance and close > resistance:
        return "above_resistance"
    if support and resistance:
        return "inside_channel"
    return "unknown"


def _build_overlays(
    bars: list[DailyBar],
    support: dict | None,
    resistance: dict | None,
    levels: list[dict],
    entry: float | None,
    stop: float | None,
    target: float | None,
) -> list[ChartOverlay]:
    overlays: list[ChartOverlay] = []
    last_index = len(bars) - 1

    def line_overlay(line: dict, oid: str, label: str, color: str) -> ChartOverlay:
        p1 = line["p1"]
        end_value = _line_value(line, last_index)
        return ChartOverlay(
            id=oid,
            kind="trend_line",
            name="segment",
            label=label,
            points=[
                ChartPoint(date=bars[p1.index].date, value=round(p1.price, 3)),
                ChartPoint(date=bars[last_index].date, value=round(end_value, 3)),
            ],
            styles={"line": {"color": color, "size": 2}},
        )

    if support:
        overlays.append(line_overlay(support, "support-line", "上升支撑线", "#1f9d55"))
    if resistance:
        overlays.append(line_overlay(resistance, "resistance-line", "下降压力线", "#d64545"))

    for i, level in enumerate(levels):
        color = "#d64545" if level["kind"] == "resistance" else "#1f9d55"
        if level["kind"] == "volume_level":
            color = "#8067dc"
        overlays.append(
            ChartOverlay(
                id=f"key-level-{i}",
                kind=level["kind"],
                name="horizontalStraightLine",
                label=level["kind"],
                points=[ChartPoint(date=bars[min(level["index"], last_index)].date, value=round(level["price"], 3))],
                styles={"line": {"color": color, "size": 1, "style": "dashed"}},
            )
        )

    for oid, label, price, color in [
        ("entry", "突破买点", entry, "#0f7bf2"),
        ("stop", "止损", stop, "#e05656"),
        ("target", "止盈", target, "#0b8f5a"),
    ]:
        if price:
            overlays.append(
                ChartOverlay(
                    id=oid,
                    kind=oid,
                    name="priceLine",
                    label=label,
                    points=[ChartPoint(date=bars[last_index].date, value=round(price, 3))],
                    styles={"line": {"color": color, "size": 1.5}},
                )
            )

    return overlays
