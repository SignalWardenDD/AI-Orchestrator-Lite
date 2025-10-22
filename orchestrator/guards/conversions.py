from __future__ import annotations
from ..utils.types import SignalCandidate

RETEST_PULL_ATR = 0.25


def to_retest(candidate: SignalCandidate) -> SignalCandidate:
    c = candidate
    # Сдвиг entry в сторону EMA20 на 0.25×ATR
    if c.side == "LONG":
        c.entry_price = max(c.entry_price - RETEST_PULL_ATR * c.atr, c.ema20)
    else:
        c.entry_price = min(c.entry_price + RETEST_PULL_ATR * c.atr, c.ema20)
    c.meta["retest"] = 1.0
    return c

def to_mr_inversion(candidate: SignalCandidate) -> SignalCandidate:
    c = candidate
    c.side = "SHORT" if c.side == "LONG" else "LONG"
    c.type = "PB"  # инверсия в MR‑идею
    c.meta["inversion"] = 1.0
    return c

def to_trend_from_pb(candidate: SignalCandidate) -> SignalCandidate:
    c = candidate
    c.type = "TRND"
    c.meta["trend_from_pb"] = 1.0
    return c
