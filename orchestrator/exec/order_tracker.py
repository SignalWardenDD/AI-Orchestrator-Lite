from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import time
from .order_tags import ROLE_ENTRY, ROLE_SL, ROLE_TP1, ROLE_TP2

@dataclass
class TrackedOrder:
    symbol: str
    side: str        # LONG/SHORT
    order_id: str
    entry_limit: float
    qty: float
    placed_ts: float
    ttl_sec: int
    atr: float
    ema20: float
    role: str = "GENERIC"
    reduce_only: bool = False

class OrderTracker:
    def __init__(self):
        self.by_id: Dict[str, TrackedOrder] = {}
        self.pending_entries: Dict[str, TrackedOrder] = {}
        self.stops: Dict[str, TrackedOrder] = {}
        self.take_profits: Dict[str, List[TrackedOrder]] = {}

    def add(self, t: TrackedOrder) -> None:
        self.by_id[t.order_id] = t

    def pop(self, order_id: str) -> Optional[TrackedOrder]:
        return self.by_id.pop(order_id, None)

    def pending(self):
        return list(self.by_id.values())

    def expired(self):
        now = time.time()
        return [t for t in self.by_id.values() if now - t.placed_ts >= t.ttl_sec]

    def register_entry(self, order: TrackedOrder):
        """Регистрирует ордер входа."""
        sym = order.symbol
        order.role = ROLE_ENTRY
        self.pending_entries[sym] = order
        self.add(order)

    def register_stop(self, order: TrackedOrder):
        """Регистрирует стоп-лосс ордер."""
        sym = order.symbol
        order.role = ROLE_SL
        self.stops[sym] = order
        self.add(order)

    def register_tp(self, order: TrackedOrder):
        """Регистрирует тейк-профит ордер."""
        sym = order.symbol
        # назначаем TP1/TP2 по количеству открытых TP
        role = ROLE_TP1 if len(self.take_profits.get(sym, [])) == 0 else ROLE_TP2
        order.role = role
        if sym not in self.take_profits:
            self.take_profits[sym] = []
        self.take_profits[sym].append(order)
        self.add(order)

    def best_sl_price(self, symbol: str) -> float:
        """Возвращает текущую 'лучшую' цену SL для символа в терминах 'не хуже чем было'."""
        ord_ = self.stops.get(symbol)
        return ord_.entry_limit if ord_ else float("-inf")

    def cancel_and_replace_sl(self, symbol: str, new_price: float):
        """Отменяет старый SL и создает новый."""
        old_sl = self.stops.get(symbol)
        if old_sl:
            # Отменяем старый SL (здесь должен быть вызов broker.cancel_order)
            self.stops.pop(symbol, None)
            self.by_id.pop(old_sl.order_id, None)
        
        # Создаем новый SL (здесь должен быть вызов broker.place_reduce_only_stop)
        # Это будет сделано в reconciler
