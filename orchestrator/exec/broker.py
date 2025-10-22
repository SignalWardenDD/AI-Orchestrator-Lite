from __future__ import annotations
from typing import Any, Dict
from .binance_rest import BinanceREST

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
    def place_postonly_limit(self, symbol: str, side: str, qty: float, price: float, ttl_sec: int) -> Dict[str, Any]:
        # На фьючерсах нет настоящего PostOnly через публичный флаг — используем GTC и проверку попадания в книгу (упрощение)
        return self.api.order(symbol=symbol, side=side, type_="LIMIT", quantity=qty, price=price, time_in_force="GTC")

    def place_market(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        return self.api.order(symbol=symbol, side=side, type_="MARKET", quantity=qty)

    def place_reduce_only(self, symbol: str, side: str, qty: float, price: float, kind: str) -> Dict[str, Any]:
        return self.api.order(symbol=symbol, side=side, type_="LIMIT", quantity=qty, price=price, time_in_force="GTC", reduce_only=True)

    def get_open_orders(self, symbol: str) -> list[Dict[str, Any]]:
        return self.api.open_orders(symbol)

    def cancel_order(self, symbol: str, order_id: str) -> None:
        self.api.cancel(symbol, order_id)

    # --- ACCOUNT ---
    def position_info(self, symbol: str) -> Dict[str, Any]:
        ps = self.api.position_info(symbol)
        return ps[0] if ps else {}
