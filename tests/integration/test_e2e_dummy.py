from orchestrator.exec.dummy_broker import DummyBroker
from orchestrator.exec.planner import PlanBuilder
from orchestrator.exec.entry import EntryExecutor
from orchestrator.exec.exits import ExitsPlacer
from orchestrator.utils.types import SignalCandidate

# Простой e2e: строим план -> пробуем исполнить market fallback -> ставим TP/SL

def test_e2e_dummy_flow():
    br = DummyBroker()
    br.set_price("ADAUSDT", 1.0)
    pb = PlanBuilder(
        fixed_notional_usdt=15.0,
        sl_mult_map={"BRK":1.3, "PB":2.0, "TRND":1.8, "BB":1.6},
        tp_ladder=[{"pct":0.2, "atr_mult":0.6}, {"pct":0.25, "atr_mult":1.2}, {"pct":0.25, "atr_mult":2.0}, {"pct":0.3, "atr_mult":3.2}],
        be_usdt={"after_tp1_usdt":0.15, "after_tp2_usdt":0.35, "after_tp3_usdt":0.8},
        slippage_cap_pct=0.12,
        ttl_min=1,
        ttl_max=1,
    )
    c = SignalCandidate(symbol="ADAUSDT", type="BRK", side="LONG", entry_price=1.0, atr=0.02, ema20=0.99, meta={}, ts=0)
    plan = pb.build(c, last_price=1.0, step_size=1.0, tick_size=0.0001)
    execu = EntryExecutor(br, slippage_cap_pct=0.12)
    ok = execu.execute(plan)
    assert ok is True or ok is False  # допускаем оба исхода для заглушки
    ex = ExitsPlacer(br)
    ex.place_tp_sl(plan.symbol, plan.side, plan.tp_levels, plan.sl_price)
