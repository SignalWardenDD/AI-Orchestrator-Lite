from __future__ import annotations
from typing import List
from .base import SignalProvider
from ..utils.types import SignalCandidate

MR_WINDOW_BARS = 4     # окно 3–4 бара
REQ_HOOK = True
TAIL_ATR_MIN = 0.6     # прокси через dist_to_ema20_atr и положение к BB

class PullbackMRProvider(SignalProvider):
    type_name = "PB"

    def generate(self, symbol: str, frows: list[dict]) -> List[SignalCandidate]:
        out: List[SignalCandidate] = []
        if len(frows) < 30:
            return out
        r = frows[-1]
        a = r["atr14"]
        ema20 = r["ema20"]
        rsi2 = r.get("rsi2", 50.0)
        rsi14 = r.get("rsi14", 50.0)
        dist_atr = r.get("dist_to_ema20_atr", 0.0)
        close = r["close"]
        bb_up = r.get("bb_up", ema20 + 2*a)
        bb_low = r.get("bb_low", ema20 - 2*a)
        natr = r.get("natr14_pct", 0.0)

        # Требуем hook: разворот RSI2 к среднему
        if REQ_HOOK:
            # простой хук: предыдущее значение в экстремуме, текущее — разворот внутрь
            if len(frows) < 3:
                return out
            prev = frows[-2]
            prev_rsi2 = prev.get("rsi2", 50.0)
            hook_long = prev_rsi2 <= 10.0 and rsi2 > prev_rsi2
            hook_short = prev_rsi2 >= 90.0 and rsi2 < prev_rsi2
        else:
            hook_long = rsi2 <= 10.0
            hook_short = rsi2 >= 90.0

        # ЛОНГ PB: RSI2<=10 при бычьем фоне (EMA20 вверх) и отскок от нижней BB
        if hook_long and (close < bb_low) or (dist_atr > 1.3 and close < ema20):
            meta = {
                "natr14_pct": natr,
                "hook": 1.0,
                "dist_to_ema20_atr": dist_atr,
            }
            out.append(SignalCandidate(
                symbol=symbol,
                type="PB",
                side="LONG",
                entry_price=close,
                atr=a,
                ema20=ema20,
                meta=meta,
                ts=r["ts"],
            ))

        # ШОРТ PB: RSI2>=90 при медвежьем фоне и отскок от верхней BB
        if hook_short and (close > bb_up) or (dist_atr > 1.3 and close > ema20):
            meta = {
                "natr14_pct": natr,
                "hook": 1.0,
                "dist_to_ema20_atr": dist_atr,
            }
            out.append(SignalCandidate(
                symbol=symbol,
                type="PB",
                side="SHORT",
                entry_price=close,
                atr=a,
                ema20=ema20,
                meta=meta,
                ts=r["ts"],
            ))
        return out
