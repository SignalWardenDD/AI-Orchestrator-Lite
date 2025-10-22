from __future__ import annotations
from typing import Iterable, List
from ..utils.types import SignalCandidate, FirstHitForecast

_TYPE_PROFILE = {
    "BRK": {"tp": (0.30, 0.22, 0.12, 0.06), "sl": 0.30, "t": (2.0, 3.0, 5.0, 8.0, 2.5)},
    "PB":  {"tp": (0.28, 0.20, 0.10, 0.05), "sl": 0.37, "t": (2.5, 3.5, 5.5, 9.0, 2.0)},
    "TRND":{"tp": (0.26, 0.22, 0.14, 0.08), "sl": 0.30, "t": (3.0, 4.0, 6.0, 9.0, 3.0)},
    "BB":  {"tp": (0.24, 0.18, 0.10, 0.06), "sl": 0.42, "t": (2.0, 3.0, 5.0, 8.0, 1.8)},
}

class NoMLForecaster:
    def predict_many(self, candidates: Iterable[SignalCandidate], horizons: List[int]) -> List[FirstHitForecast]:
        out: List[FirstHitForecast] = []
        for c in candidates:
            prof = _TYPE_PROFILE.get(c.type, _TYPE_PROFILE["BB"])
            tp1, tp2, tp3, tp4 = prof["tp"]
            slp = prof["sl"]
            for H in horizons:
                out.append(FirstHitForecast(
                    symbol=c.symbol,
                    type=c.type,
                    side=c.side,
                    H=H,
                    p_hit={"tp1":tp1,"tp2":tp2,"tp3":tp3,"tp4":tp4,"sl":slp},
                    t_hit={"tp1":2.0,"tp2":3.0,"tp3":5.0,"tp4":8.0,"sl":2.5},
                    fill_prob=0.68,
                    slip_est=0.0009,
                    conf_type=0.35,
                    flags={}
                ))
        return out
