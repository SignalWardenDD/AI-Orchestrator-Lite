from __future__ import annotations
from typing import Any, Dict
import time
from .binance_rest import BinanceREST
from .order_tags import make_cid

class Broker:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None, base_url: str | None = None):
        if not api_key or not api_secret:
            raise ValueError("API keys required for live Broker")
        self.api = BinanceREST(api_key, api_secret, base_url or "https://fapi.binance.com")

    # --- MARKET DATA ---
    def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 500) -> list[list]:
        return self.api.klines(symbol, interval, limit)

    def fetch_price(self, symbol: str) -> float:
        return self.api.ticker_price(symbol)

    def fetch_exchange_info(self) -> Dict[str, Any]:
        return self.api.exchange_info()

    # --- ORDERS ---
    def place_postonly_limit(self, symbol: str, side: str, qty: float, price: float, ttl_sec: int, use_limit_maker: bool = False, role: str = "ENTRY") -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        client_order_id = make_cid(symbol, role, now_ms)
        
        if use_limit_maker:
            # Настоящие maker-ордера на Binance Futures
            return self.api.order(symbol=symbol, side=side, type_="LIMIT_MAKER", quantity=qty, price=price, new_client_order_id=client_order_id)
        else:
            # Fallback к GTC
            return self.api.order(symbol=symbol, side=side, type_="LIMIT", quantity=qty, price=price, time_in_force="GTC", new_client_order_id=client_order_id)

    def place_market(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        return self.api.order(symbol=symbol, side=side, type_="MARKET", quantity=qty)

    def place_reduce_only(self, symbol: str, side: str, qty: float, price: float, kind: str, role: str = "TP") -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        client_order_id = make_cid(symbol, role, now_ms)
        return self.api.order(symbol=symbol, side=side, type_="LIMIT", quantity=qty, price=price, time_in_force="GTC", reduce_only=True, new_client_order_id=client_order_id)

    def place_reduce_only_stop(self, symbol: str, side: str, qty: float, stop_price: float, role: str = "SL") -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        client_order_id = make_cid(symbol, role, now_ms)
        return self.api.order(symbol=symbol, side=side, type_="STOP_MARKET", quantity=qty, stop_price=stop_price, reduce_only=True, new_client_order_id=client_order_id)

    def get_open_orders(self, symbol: str) -> list[Dict[str, Any]]:
        return self.api.open_orders(symbol)

    def list_open_orders(self, symbol: str) -> list[Dict[str, Any]]:
        """Алиас для get_open_orders для совместимости с reconciler."""
        return self.api.open_orders(symbol)

    def cancel_order(self, symbol: str, order_id: str) -> None:
        self.api.cancel(symbol, order_id)

    # --- ACCOUNT ---
    def position_info(self, symbol: str) -> Dict[str, Any]:
        ps = self.api.position_info(symbol)
        return ps[0] if ps else {}
