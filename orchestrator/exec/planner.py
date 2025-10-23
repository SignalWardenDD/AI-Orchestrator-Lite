from __future__ import annotations
from typing import List, Tuple
from ..utils.types import SignalCandidate, ExecutionPlan
from ..risk.sizing import qty_from_notional
from .pnl import compute_price_for_pnl
from .utils import opposite

# Параметры подаются снаружи из конфигов (risk + ladders + sl_multipliers)

class PlanBuilder:
    def __init__(self, fixed_notional_usdt: float, sl_mult_map: dict[str, float], tp_ladder: list[dict], be_usdt: dict, slippage_cap_pct: float, ttl_min: int, ttl_max: int, partial_tps: list[dict] = None, base_stop_usd: float = None):
        self.fixed = fixed_notional_usdt
        self.sl_mult = sl_mult_map
        self.tp_ladder = tp_ladder
        self.be_usdt = be_usdt
        self.slip_cap = slippage_cap_pct
        self.ttl_min = ttl_min
        self.ttl_max = ttl_max
        self.partial_tps = partial_tps or []
        self.base_stop_usd = base_stop_usd

    def _tp_prices_and_sizes(self, side: str, entry: float, atr: float, qty: float) -> List[tuple]:
        levels: List[tuple] = []
        
        # Приоритет: PnL-таргеты > ATR-лесенка
        if self.partial_tps:
            for tp_config in self.partial_tps:
                share = float(tp_config.get("share", 0.0))
                pnl_usd = float(tp_config.get("from_entry_usd", 0.0))
                price = compute_price_for_pnl(entry, qty, side, pnl_usd)
                leg_qty = round(qty * share, 8)
                levels.append((price, leg_qty))
        else:
            # Fallback к ATR-лесенке
            for leg in self.tp_ladder:
                pct = float(leg.get("pct", 0.0))
                mult = float(leg.get("atr_mult", 0.0))
                delta = mult * atr
                price = entry + delta if side == "LONG" else entry - delta
                leg_qty = round(qty * pct, 8)
                levels.append((price, leg_qty))
        return levels

    def _sl_price(self, typ: str, side: str, entry: float, atr: float) -> float:
        # Приоритет: PnL-таргет > ATR-мультипликатор
        if self.base_stop_usd is not None:
            return compute_price_for_pnl(entry, 1.0, side, self.base_stop_usd)
        else:
            # Fallback к ATR-мультипликатору
            mult = float(self.sl_mult.get(typ, 1.6))
            delta = mult * atr
            return entry - delta if side == "LONG" else entry + delta

    def build(self, c: SignalCandidate, last_price: float, step_size: float, tick_size: float) -> ExecutionPlan:
        # Квота: фикс номинал / last_price → округлить к шагу лота
        qty = qty_from_notional(price=last_price, notional_usdt=self.fixed, step_size=step_size)
        entry = c.entry_price
        atr = c.atr
        tp_levels = self._tp_prices_and_sizes(c.side, entry, atr, qty)
        sl_price = self._sl_price(c.type, c.side, entry, atr)
        ttl = max(self.ttl_min, min(self.ttl_max, int(c.meta.get("ttl", self.ttl_max))))
        return ExecutionPlan(
            symbol=c.symbol,
            side=c.side,
            qty=qty,
            entry_limit=entry,
            ttl_sec=ttl,
            market_fallback_cap=self.slip_cap,
            tp_levels=tp_levels,
            sl_price=sl_price,
        )

def plan_entry(signal: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Планирует вход в позицию."""
    planner = PlanBuilder(
        fixed_notional_usdt=config.get('fixed_notional_usdt', 15.0),
        sl_mult_map=config.get('sl_multipliers', {}),
        tp_ladder=config.get('tp_ladder', []),
        be_usdt=config.get('be_levels', {}),
        slippage_cap_pct=config.get('slippage_cap_pct', 0.12),
        ttl_min=config.get('ttl_min', 8),
        ttl_max=config.get('ttl_max', 12),
        partial_tps=config.get('partial_tps', []),
        base_stop_usd=config.get('base_stop_usd', -0.35)
    )
    return planner.build(signal)
