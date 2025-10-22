from __future__ import annotations
from typing import Tuple
from ..utils.types import SignalCandidate

class RecheckResult:
    def __init__(self, freshness: float, decision: str, reason: str | None = None):
        self.freshness = freshness
        self.decision = decision  # valid/adapt/cancel
        self.reason = reason

# Пороговые значения из спецификации
FRESH_CANCEL_GT = 0.5
FRESH_ADAPT_MIN = 0.3


def _ema20_slope(frows: list[dict]) -> float:
    if len(frows) < 2:
        return 0.0
    return frows[-1].get("ema20", 0.0) - frows[-2].get("ema20", 0.0)


def realtime_recheck(candidate: SignalCandidate, recent_15m: list[dict], recent_1h: list[dict]) -> RecheckResult:
    # Быстрые проверки: разворот EMA20, RSI2 перекрут, уход от entry, «факел» 15m
    reason = []
    fresh = 0.0

    # Направление/наклон
    slope1h = _ema20_slope(recent_1h[-2:])
    if candidate.side == "LONG" and slope1h < 0:
        fresh += 0.25; reason.append("ema20_down")
    if candidate.side == "SHORT" and slope1h > 0:
        fresh += 0.25; reason.append("ema20_up")

    # Дистанция к entry: ушли >0.3×ATR от уровня
    if recent_1h:
        last = recent_1h[-1]
        dist = abs(last.get("close", candidate.entry_price) - candidate.entry_price) / max(candidate.atr, 1e-9)
        if dist > 0.3:
            fresh += 0.25; reason.append("far_from_entry")

    # RSI2 перекрут
    if len(recent_1h) >= 3:
        rsi2_prev = recent_1h[-2].get("rsi2", 50.0)
        rsi2_last = recent_1h[-1].get("rsi2", 50.0)
        if rsi2_prev <= 20.0 and rsi2_last >= 80.0:
            fresh += 0.25; reason.append("rsi2_flip_up")
        if rsi2_prev >= 80.0 and rsi2_last <= 20.0:
            fresh += 0.25; reason.append("rsi2_flip_down")

    # «Факел» 15m: большой корпус без хвоста (прокси: |close-ema20|/ATR15m > 1.4)
    if recent_15m:
        r15 = recent_15m[-1]
        atr15 = r15.get("atr14", 0.0)
        if atr15 > 0:
            dist_15 = abs(r15.get("close", 0.0) - r15.get("ema20", 0.0)) / atr15
            if dist_15 > 1.4:
                fresh += 0.2; reason.append("torch15m")

    decision = "valid"
    if fresh > FRESH_CANCEL_GT:
        decision = "cancel"
    elif fresh >= FRESH_ADAPT_MIN:
        decision = "adapt"

    return RecheckResult(freshness=min(1.0, fresh), decision=decision, reason=",".join(reason) or None)
