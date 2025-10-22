from __future__ import annotations
import time, hmac, hashlib, urllib.parse, json
from typing import Any, Dict, List, Optional
import requests

# Минимальная обёртка для Binance Futures (USDT‑M) REST‑only

class BinanceREST:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://fapi.binance.com", recv_window: int = 5000, timeout: int = 10):
        self.key = api_key
        self.secret = api_secret.encode("utf-8")
        self.base = base_url.rstrip("/")
        self.recv_window = recv_window
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.headers.update({"X-MBX-APIKEY": self.key})

    # --- helpers ---
    def _sign(self, params: dict) -> dict:
        params = dict(params)
        params.update({"timestamp": int(time.time()*1000), "recvWindow": self.recv_window})
        q = urllib.parse.urlencode(params, doseq=True)
        sig = hmac.new(self.secret, q.encode("utf-8"), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _get(self, path: str, params: Optional[dict] = None, signed: bool = False):
        url = f"{self.base}{path}"
        p = params or {}
        if signed:
            p = self._sign(p)
        r = self.sess.get(url, params=p, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, params: Optional[dict] = None, signed: bool = True):
        url = f"{self.base}{path}"
        p = params or {}
        if signed:
            p = self._sign(p)
        r = self.sess.post(url, data=p, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str, params: Optional[dict] = None, signed: bool = True):
        url = f"{self.base}{path}"
        p = params or {}
        if signed:
            p = self._sign(p)
        r = self.sess.delete(url, data=p, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # --- market data ---
    def klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> List[List[Any]]:
        return self._get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})

    def ticker_price(self, symbol: str) -> float:
        j = self._get("/fapi/v1/ticker/price", {"symbol": symbol})
        return float(j["price"]) if isinstance(j, dict) else float(j[0]["price"])  # API иногда возвращает массив

    def exchange_info(self) -> dict:
        return self._get("/fapi/v1/exchangeInfo")

    # --- account/orders ---
    def position_info(self, symbol: Optional[str] = None) -> list[dict]:
        data = self._get("/fapi/v2/positionRisk", signed=True)
        if symbol:
            return [p for p in data if p.get("symbol") == symbol]
        return data

    def open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        params = {"symbol": symbol} if symbol else {}
        return self._get("/fapi/v1/openOrders", params=params, signed=True)

    def order(self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None, time_in_force: Optional[str] = None, reduce_only: Optional[bool] = None) -> dict:
        params = {"symbol": symbol, "side": side, "type": type_, "quantity": quantity}
        if price is not None:
            params["price"] = price
        if time_in_force:
            params["timeInForce"] = time_in_force
        if reduce_only is not None:
            params["reduceOnly"] = "true" if reduce_only else "false"
        return self._post("/fapi/v1/order", params=params, signed=True)

    def cancel(self, symbol: str, order_id: str) -> dict:
        return self._delete("/fapi/v1/order", params={"symbol": symbol, "orderId": order_id}, signed=True)
