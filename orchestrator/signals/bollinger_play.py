from __future__ import annotations
from typing import List
from .base import SignalProvider
from ..utils.types import SignalCandidate

SQUEEZE_PCT = 0.70
BANDWIDTH_BOOM = 2.5  # >250% медианы — уже-взрыв

class BollingerPlayProvider(SignalProvider):
    type_name = "BB"

    def generate(self, symbol: str, frows: list[dict]) -> List[SignalCandidate]:
        out: List[SignalCandidate] = []
        if len(frows) < 40:
            return out
        bw = [r.get("bb_bw", 0.0) for r in frows]
        med_bw = sorted(bw[-40:])[20] if len(bw) >= 40 else (sorted(bw)[len(bw)//2] if bw else 0.0)
        r = frows[-1]
        a = r["atr14"]
        close = r["close"]
        ema20 = r["ema20"]
        last_bw = r.get("bb_bw", 0.0)
        bb_up = r.get("bb_up", ema20 + 2*a)
        bb_low = r.get("bb_low", ema20 - 2*a)

        if last_bw > BANDWIDTH_BOOM * med_bw:
            # уже-взрыв → для BRK используем retest‑идею, для MR — от бойниц
            # Здесь создадим MR‑кандидата, если есть отбой от границы
            if close < bb_low:
                out.append(SignalCandidate(symbol=symbol, type="BB", side="LONG", entry_price=close, atr=a, ema20=ema20, meta={"boom":1.0}, ts=r["ts"]))
            elif close > bb_up:
                out.append(SignalCandidate(symbol=symbol, type="BB", side="SHORT", entry_price=close, atr=a, ema20=ema20, meta={"boom":1.0}, ts=r["ts"]))
            return out

        # Squeeze→break или mean‑revert в зависимости от положения
        if last_bw <= SQUEEZE_PCT * med_bw:
            if close > bb_up:
                out.append(SignalCandidate(symbol=symbol, type="BB", side="LONG", entry_price=close, atr=a, ema20=ema20, meta={"squeeze":1.0}, ts=r["ts"]))
            elif close < bb_low:
                out.append(SignalCandidate(symbol=symbol, type="BB", side="SHORT", entry_price=close, atr=a, ema20=ema20, meta={"squeeze":1.0}, ts=r["ts"]))
        else:
            # без squeeze — играть от границ в MR‑стиле
            if close < bb_low:
                out.append(SignalCandidate(symbol=symbol, type="BB", side="LONG", entry_price=close, atr=a, ema20=ema20, meta={}, ts=r["ts"]))
            elif close > bb_up:
                out.append(SignalCandidate(symbol=symbol, type="BB", side="SHORT", entry_price=close, atr=a, ema20=ema20, meta={}, ts=r["ts"]))
        return out

def compute_marks(kline: pd.DataFrame) -> pd.Series:
    """Вычисляет метки сигналов Bollinger."""
    provider = BollingerPlayProvider()
    return provider.generate(kline)
