from __future__ import annotations
from typing import List
from .base import SignalProvider
from .helpers import rolling_max, rolling_min, median, nr7_like
from ..utils.types import SignalCandidate, Side

CALM_NATR_PCT = 0.8  # TODO: из конфигов
SQUEEZE_PCT = 0.70   # bandwidth <= 70% медианы
C_A = 1.2            # SMA20 ± c×ATR — прибл. буферы через EMA20
C_B = 1.3

class BreakoutProvider(SignalProvider):
    type_name = "BRK"

    def __init__(self, group: str):
        self.group = group  # "A" | "B"

    def generate(self, symbol: str, frows: list[dict]) -> List[SignalCandidate]:
        out: List[SignalCandidate] = []
        if len(frows) < 40:
            return out
        closes = [r["close"] for r in frows]
        atr = [r["atr14"] for r in frows]
        bw = [r.get("bb_bw", 0.0) for r in frows]
        ema20 = [r["ema20"] for r in frows]
        rsi2 = [r.get("rsi2", 50.0) for r in frows]
        natr = [r.get("natr14_pct", 0.0) for r in frows]

        don_hi = rolling_max(closes, 10)
        don_lo = rolling_min(closes, 10)
        nr7 = nr7_like([max(1e-9, r.get("bb_up", 0.0) - r.get("bb_low", 0.0)) for r in frows], 7)
        med_bw = median(bw[-40:]) if len(bw) >= 40 else median(bw)
        last = frows[-1]
        a = last["atr14"]
        last_bw = last.get("bb_bw", 0.0)
        last_close = last["close"]
        last_ema20 = last["ema20"]
        last_rsi2 = last.get("rsi2", 50.0)
        last_natr = last.get("natr14_pct", 0.0)

        # Фильтры опасности
        if last_natr < CALM_NATR_PCT:
            # calm‑пила → пропускаем BRK
            return out

        squeeze_ok = (last_bw <= SQUEEZE_PCT * med_bw) or nr7[-1]
        if not squeeze_ok:
            return out

        # Пробойные уровни относительно EMA20 ± c×ATR (приближение SMA20±c*ATR)
        c_mult = C_A if self.group == "A" else C_B
        up_th = last_ema20 + c_mult * a
        dn_th = last_ema20 - c_mult * a

        # Ложный «факел»: RSI2 экстремум — отдадим на retest/guard
        fakel = (last_rsi2 >= 95.0) or (last_rsi2 <= 5.0)

        # ЛОНГ пробой: close > Donchian10_hi или выше буфера EMA20+c*ATR
        if last_close > max(don_hi[-1], up_th):
            meta = {
                "natr14_pct": last_natr,
                "bb_bw": last_bw,
                "retest_only": 1.0 if fakel else 0.0,
                "don_hi": don_hi[-1],
            }
            out.append(SignalCandidate(
                symbol=symbol,
                type="BRK",
                side="LONG",
                entry_price=last_close,
                atr=a,
                ema20=last_ema20,
                meta=meta,
                ts=last["ts"],
            ))

        # ШОРТ пробой
        if last_close < min(don_lo[-1], dn_th):
            meta = {
                "natr14_pct": last_natr,
                "bb_bw": last_bw,
                "retest_only": 1.0 if fakel else 0.0,
                "don_lo": don_lo[-1],
            }
            out.append(SignalCandidate(
                symbol=symbol,
                type="BRK",
                side="SHORT",
                entry_price=last_close,
                atr=a,
                ema20=last_ema20,
                meta=meta,
                ts=last["ts"],
            ))
        return out

def compute_marks(kline: pd.DataFrame) -> pd.Series:
    """Вычисляет метки сигналов прорыва."""
    provider = BreakoutProvider()
    return provider.generate(kline)
