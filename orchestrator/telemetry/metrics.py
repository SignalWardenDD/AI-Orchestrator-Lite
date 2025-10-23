from __future__ import annotations
from typing import Optional
import time

_store = None
_tracker = None


def set_state_store(store):
    global _store
    _store = store


def set_order_tracker(tracker):
    global _tracker
    _tracker = tracker


def snapshot() -> dict:
    s = _store
    t = _tracker
    return {
        "positions": len(s.positions) if s else 0,
        "day_realized_usdt": getattr(s, "day_realized_usdt", 0.0) if s else 0.0,
        "paused_symbols": list(getattr(s, "paused_symbols", [])) if s else [],
        "pending_limits": len(t.pending()) if t else 0,
    }

class MetricsCollector:
    """Сборщик метрик."""
    
    def __init__(self):
        self.signals = []
        self.trades = []
    
    def record_signal(self, symbol: str, signal_type: str, side: str, ev: float):
        """Записывает сигнал."""
        self.signals.append({
            'symbol': symbol,
            'type': signal_type,
            'side': side,
            'ev': ev,
            'timestamp': time.time()
        })
    
    def record_trade(self, symbol: str, side: str, price: float, qty: float, pnl: float):
        """Записывает сделку."""
        self.trades.append({
            'symbol': symbol,
            'side': side,
            'price': price,
            'qty': qty,
            'pnl': pnl,
            'timestamp': time.time()
        })
