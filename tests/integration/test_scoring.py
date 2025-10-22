from orchestrator.auction.scorer import score_candidates
from orchestrator.utils.types import SignalCandidate, FirstHitForecast

def dummy():
    c = SignalCandidate(symbol="ADAUSDT", type="BRK", side="LONG", entry_price=1.0, atr=0.02, ema20=1.0, meta={"natr14_pct":1.0}, ts=0)
    f = FirstHitForecast(symbol="ADAUSDT", type="BRK", side="LONG", H=4,
                         p_hit={"tp1":0.3,"tp2":0.2,"tp3":0.1,"tp4":0.05,"sl":0.35},
                         t_hit={"tp1":2,"tp2":3,"tp3":5,"tp4":7,"sl":2.5},
                         fill_prob=0.7, slip_est=0.0008, conf_type=0.5, flags={})
    out = score_candidates([c], [f], btc_weight=0.5)
    assert len(out) == 1
