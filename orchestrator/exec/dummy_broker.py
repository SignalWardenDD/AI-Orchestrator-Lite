from __future__ import annotations
from typing import Any, Dict, List
import time

class DummyBroker:
    def __init__(self):
        self.orders: Dict[str, List[dict]] = {}
        self.prices: Dict[str, float] = {}

    def set_price(self, symbol: str, price: float):
        self.prices[symbol] = price

    def fetch_price(self, symbol: str) -> float:
        return self.prices.get(symbol, 0.0)

    def place_postonly_limit(self, symbol: str, side: str, qty: float, price: float, ttl_sec: int) -> dict:
        o = {"orderId": f"LIM-{int(time.time()*1000)}", "symbol": symbol, "side": side, "qty": qty, "price": price, "postOnly": True, "ttl": ttl_sec, "filled": False}
        self.orders.setdefault(symbol, []).append(o)
        return o

    def cancel_order(self, symbol: str, order_id: str) -> None:
        arr = self.orders.get(symbol, [])
        for o in arr:
            if o.get("orderId") == order_id:
                o["canceled"] = True
                return

    def place_market(self, symbol: str, side: str, qty: float) -> dict:
        return {"orderId": f"MKT-{int(time.time()*1000)}", "symbol": symbol, "side": side, "qty": qty, "price": self.fetch_price(symbol)}

    def place_reduce_only(self, symbol: str, side: str, qty: float, price: float, kind: str) -> dict:
        return {"orderId": f"RED-{int(time.time()*1000)}", "symbol": symbol, "side": side, "qty": qty, "price": price, "kind": kind}

    def get_open_orders(self, symbol: str) -> list[dict]:
        return [o for o in self.orders.get(symbol, []) if not o.get("canceled") and not o.get("filled")]
