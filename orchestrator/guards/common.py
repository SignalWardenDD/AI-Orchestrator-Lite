from __future__ import annotations
from typing import Tuple
from ..utils.types import SignalCandidate, GuardDecision

CALM_NATR_PCT = 0.8
EDGE_BODY_ATR = 1.4     # прокси через dist_to_ema и rsi2 экстрем
DIST_EMA20_ATR_MIN = 1.2
RSI2_EXT = {"hi": 98.0, "lo": 2.0}


def edge_guard(c: SignalCandidate) -> Tuple[GuardDecision, dict]:
    meta = c.meta or {}
    rsi2 = meta.get("rsi2", 50.0)
    dist = meta.get("dist_to_ema20_atr", 0.0)
    # Если очень далеко от EMA20 и RSI2 экстремален — опасный край
    if dist >= DIST_EMA20_ATR_MIN and (rsi2 >= RSI2_EXT["hi"] or rsi2 <= RSI2_EXT["lo"]):
        return GuardDecision.ADAPT, {"edge": True}
    return GuardDecision.ACCEPT, {}


def calm_active_penalty(c: SignalCandidate) -> float:
    natr = c.meta.get("natr14_pct", 0.0)
    if c.type == "BRK" and natr < CALM_NATR_PCT:
        return 0.9  # мягкий штраф
    return 1.0
