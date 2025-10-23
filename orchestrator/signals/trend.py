from __future__ import annotations
from typing import List
from .base import SignalProvider
from ..utils.types import SignalCandidate

ADX_MIN = 18.0
MICRO_PULL_ATR = (0.2, 0.3)

class TrendProvider(SignalProvider):
    type_name = "TRND"

    def generate(self, symbol: str, frows: list[dict]) -> List[SignalCandidate]:
        out: List[SignalCandidate] = []
        if len(frows) < 210:
            return out
        r = frows[-1]
        ema50 = r.get("ema50", 0.0)
        ema200 = r.get("ema200", 0.0)
        rsi14 = r.get("rsi14", 50.0)
        adx = r.get("adx14", 20.0)
        a = r["atr14"]
        close = r["close"]
        ema20 = r["ema20"]
        dist = r.get("dist_to_ema20_atr", 0.0)

        if adx < ADX_MIN:
            return out  # сплющивание

        # LONG тренд: EMA50>EMA200 & RSI14>55 — вход после микро‑отката к EMA20/BB mid
        if ema50 > ema200 and rsi14 > 55.0 and dist >= MICRO_PULL_ATR[0] and close >= ema20:
            out.append(SignalCandidate(
                symbol=symbol,
                type="TRND",
                side="LONG",
                entry_price=close,
                atr=a,
                ema20=ema20,
                meta={"micro_pull": 1.0, "dist_to_ema20_atr": dist},
                ts=r["ts"],
            ))

        # SHORT тренд
        if ema50 < ema200 and rsi14 < 45.0 and dist >= MICRO_PULL_ATR[0] and close <= ema20:
            out.append(SignalCandidate(
                symbol=symbol,
                type="TRND",
                side="SHORT",
                entry_price=close,
                atr=a,
                ema20=ema20,
                meta={"micro_pull": 1.0, "dist_to_ema20_atr": dist},
                ts=r["ts"],
            ))
        return out

def compute_marks(kline: pd.DataFrame) -> pd.Series:
    """Вычисляет метки сигналов тренда."""
    provider = TrendProvider()
    return provider.generate(kline)
