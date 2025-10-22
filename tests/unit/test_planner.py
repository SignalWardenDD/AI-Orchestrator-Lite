from orchestrator.exec.planner import PlanBuilder
from orchestrator.utils.types import SignalCandidate

def test_plan_builder_tp_sl_prices():
    pb = PlanBuilder(
        fixed_notional_usdt=15.0,
        sl_mult_map={"BRK":1.3, "PB":2.0, "TRND":1.8, "BB":1.6},
        tp_ladder=[{"pct":0.2, "atr_mult":0.6}, {"pct":0.25, "atr_mult":1.2}],
        be_usdt={"after_tp1_usdt":0.15, "after_tp2_usdt":0.35, "after_tp3_usdt":0.8},
        slippage_cap_pct=0.12,
        ttl_min=8,
        ttl_max=12,
    )
    c = SignalCandidate(symbol="ADAUSDT", type="BRK", side="LONG", entry_price=1.0, atr=0.02, ema20=0.99, meta={}, ts=0)
    plan = pb.build(c, last_price=1.0, step_size=1.0, tick_size=0.0001)
    assert plan.tp_levels[0][0] > plan.entry_limit
    assert plan.sl_price < plan.entry_limit
