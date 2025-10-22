from __future__ import annotations
import time
from ..utils.types import ExecutionPlan

class EntryExecutor:
    def __init__(self, broker, slippage_cap_pct: float, order_tracker=None):
        self.broker = broker
        self.slip_cap = slippage_cap_pct
        self.tracker = order_tracker  # optional

    def _slippage_ok(self, expected_price: float, current_price: float) -> bool:
        if expected_price <= 0:
            return False
        slip = abs(current_price - expected_price) / expected_price * 100
        return slip <= self.slip_cap

    def place_limit_and_track(self, plan: ExecutionPlan) -> str | None:
        """Ставит postOnly LIMIT и регистрирует в трекере вместо ожидания внутри метода.
        Возвращает order_id или None.
        """
        resp = self.broker.place_postonly_limit(
            symbol=plan.symbol,
            side=("BUY" if plan.side == "LONG" else "SELL"),
            qty=plan.qty,
            price=plan.entry_limit,
            ttl_sec=plan.ttl_sec,
        )
        order_id = None
        if isinstance(resp, dict):
            order_id = str(resp.get("orderId")) if resp.get("orderId") else None
        if self.tracker and order_id:
            from .order_tracker import TrackedOrder
            self.tracker.add(TrackedOrder(
                symbol=plan.symbol,
                side=plan.side,
                order_id=order_id,
                entry_limit=plan.entry_limit,
                qty=plan.qty,
                placed_ts=time.time(),
                ttl_sec=plan.ttl_sec,
                atr=abs(plan.tp_levels[0][0] - plan.entry_limit) if plan.tp_levels else 0.0,
                ema20=0.0,
            ))
        return order_id

    def execute(self, plan: ExecutionPlan) -> bool:
        """Старый режим: поставить LIMIT, подождать TTL, при необходимости — market fallback.
        Оставлен для совместимости; при наличии order_tracker лучше вызывать place_limit_and_track.
        """
        resp = self.broker.place_postonly_limit(
            symbol=plan.symbol,
            side=("BUY" if plan.side == "LONG" else "SELL"),
            qty=plan.qty,
            price=plan.entry_limit,
            ttl_sec=plan.ttl_sec,
        )
        order_id = resp.get("orderId") if isinstance(resp, dict) else None
        t0 = time.time()
        filled = False
        while time.time() - t0 < plan.ttl_sec:
            time.sleep(0.8)
            filled = False  # TODO: опрос статуса ордера
        if filled:
            return True
        if order_id:
            try:
                self.broker.cancel_order(plan.symbol, str(order_id))
            except Exception:
                pass
        px = self.broker.fetch_price(plan.symbol)
        if not self._slippage_ok(plan.entry_limit, px):
            return False
        self.broker.place_market(plan.symbol, ("BUY" if plan.side == "LONG" else "SELL"), plan.qty)
        return True
