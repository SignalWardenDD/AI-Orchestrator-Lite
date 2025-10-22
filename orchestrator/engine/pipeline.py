from __future__ import annotations
from typing import List
from ..data.ingest import fetch_ohlcv_1h, fetch_btc_context
from ..data.features import build_feature_rows
from ..signals.breakout import BreakoutProvider
from ..signals.pullback_mr import PullbackMRProvider
from ..signals.trend import TrendProvider
from ..signals.bollinger_play import BollingerPlayProvider
from ..guards.common import edge_guard
from ..guards.conversions import to_retest, to_mr_inversion, to_trend_from_pb
from ..guards.realtime_recheck import realtime_recheck
from ..forecast.registry import ForecastRegistry
from ..forecast.no_ml import NoMLForecaster
from ..auction.scorer import score_candidates
from ..auction.selector import pick_winner
from ..exec.planner import PlanBuilder
from ..exec.entry import EntryExecutor
from ..exec.exits import ExitsPlacer
from ..telemetry.audit import audit_line
from ..utils.types import SignalCandidate
from config.loader import load_settings, load_symbols

class AnalyzePipeline:
    def __init__(self, symbols: list[str], providers, forecast_reg: ForecastRegistry, plan_builder: PlanBuilder, entry_exec: EntryExecutor, exits_placer: ExitsPlacer, store=None):
        self.symbols = symbols
        self.providers = providers
        self.forecast_reg = forecast_reg
        self.plan_builder = plan_builder
        self.entry_exec = entry_exec
        self.exits = exits_placer
        self.store = store
        self.settings = load_settings().engine
        self.no_ml = NoMLForecaster()
        self.sy = load_symbols().symbols
        self._sym_spec = {x["symbol"]: x for x in self.sy}

    def _collect_candidates(self, symbol: str) -> List[SignalCandidate]:
        if self.store and symbol in self.store.paused_symbols:
            return []
        if self.store and not self.store.get_slot_free(symbol):
            return []
        bars = fetch_ohlcv_1h(symbol, limit=220)
        frows = build_feature_rows(bars)
        cands: List[SignalCandidate] = []
        for p in self.providers:
            try:
                cands.extend(p.generate(symbol, frows))
            except Exception as e:
                audit_line(event="provider_error", symbol=symbol, provider=getattr(p, "type_name", "?"), err=str(e))
        # guards pre-filter (edge + конверсии)
        filtered: List[SignalCandidate] = []
        for c in cands:
            gd, meta = edge_guard(c)
            if gd.name == "REJECT":
                audit_line(event="guard_reject", symbol=c.symbol, type=c.type, side=c.side, reason=str(meta))
                continue
            if gd.name == "ADAPT":
                # упрощённая конверсия: сначала retest, если указан экстрем
                if c.meta.get("retest_only", 0.0) > 0:
                    c = to_retest(c)
                elif c.type == "PB" and c.meta.get("hook", 0.0) == 0.0:
                    c = to_trend_from_pb(c)
                else:
                    c = to_mr_inversion(c)
            filtered.append(c)
        return filtered

    def run_once(self):
        all_cands: List[SignalCandidate] = []
        for s in self.symbols:
            all_cands.extend(self._collect_candidates(s))
        if not all_cands:
            return
        horizons = [2,4,6,10]
        if bool(self.settings.get("forecast", {}).get("enabled", True)):
            forecasts = self.forecast_reg.forecast(all_cands, horizons)
        else:
            forecasts = self.no_ml.predict_many(all_cands, horizons)
        from ..data.ingest import fetch_btc_context, fetch_ohlcv_1h
        scored = score_candidates(all_cands, forecasts, btc_weight=fetch_btc_context().get("btc_weight", 0.5))
        winner = pick_winner(scored)
        if not winner:
            return
        # Re-Check перед входом на свежих барах
        bars_1h = fetch_ohlcv_1h(winner.symbol, limit=30)
        f1h = build_feature_rows(bars_1h)
        recent_1h = [{"ema20": r.get("ema20",0.0), "rsi2": r.get("rsi2",50.0), "close": r.get("close",0.0)} for r in f1h[-3:]]
        rr = realtime_recheck(
            candidate=next(c for c in all_cands if c.symbol==winner.symbol and c.type==winner.type and c.side==winner.side),
            recent_15m=[],
            recent_1h=recent_1h,
        )
        if rr.decision == "cancel":
            audit_line(event="recheck_cancel_pre", symbol=winner.symbol, reason=rr.reason)
            return
        # Build plan -> LIMIT & track
        last_price =  self.entry_exec.broker.fetch_price(winner.symbol)
        spec = self._sym_spec.get(winner.symbol, {"step_size": 0.001, "tick_size": 0.0001})
        step_size = float(spec.get("step_size", 0.001)); tick_size = float(spec.get("tick_size", 0.0001))
        cand = next(c for c in all_cands if (c.symbol == winner.symbol and c.type == winner.type and c.side == winner.side))
        plan = self.plan_builder.build(cand, last_price=last_price, step_size=step_size, tick_size=tick_size)
        order_id = self.entry_exec.place_limit_and_track(plan)
        if order_id:
            if self.store:
                from ..state.store import Position
                self.store.apply_fill_open(Position(symbol=plan.symbol, side=plan.side, qty_init=plan.qty, qty=plan.qty, entry_price=plan.entry_limit, ts_open=0))
            audit_line(event="limit_placed", symbol=plan.symbol, side=plan.side, order_id=order_id, price=plan.entry_limit, qty=plan.qty, pre_recheck=rr.decision)
