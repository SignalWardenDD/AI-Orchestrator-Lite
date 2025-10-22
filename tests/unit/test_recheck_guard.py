from orchestrator.guards.realtime_recheck import realtime_recheck
from orchestrator.utils.types import SignalCandidate

def test_recheck_adapt_on_slope_flip():
    c = SignalCandidate(symbol="ADAUSDT", type="BRK", side="LONG", entry_price=1.0, atr=0.02, ema20=1.0, meta={}, ts=0)
    recent_1h = [
        {"ema20": 1.0, "rsi2": 30.0, "close": 1.0},
        {"ema20": 0.99, "rsi2": 85.0, "close": 0.98},
    ]
    rr = realtime_recheck(c, recent_15m=[], recent_1h=recent_1h)
    assert rr.decision in ("adapt", "cancel")
