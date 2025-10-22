from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
import time

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

class OrderTracker:
    def __init__(self):
        self.by_id: Dict[str, TrackedOrder] = {}

    def add(self, t: TrackedOrder) -> None:
        self.by_id[t.order_id] = t

    def pop(self, order_id: str) -> Optional[TrackedOrder]:
        return self.by_id.pop(order_id, None)

    def pending(self):
        return list(self.by_id.values())

    def expired(self):
        now = time.time()
        return [t for t in self.by_id.values() if now - t.placed_ts >= t.ttl_sec]
