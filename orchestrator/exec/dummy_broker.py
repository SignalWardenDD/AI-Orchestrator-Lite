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

    def place_postonly_limit(self, symbol: str, side: str, qty: float, price: float, ttl_sec: int, use_limit_maker: bool = False, role: str = "ENTRY") -> dict:
        o = {"orderId": f"LIM-{int(time.time()*1000)}", "symbol": symbol, "side": side, "qty": qty, "price": price, "postOnly": True, "ttl": ttl_sec, "filled": False, "role": role}
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

    def place_reduce_only(self, symbol: str, side: str, qty: float, price: float, kind: str, role: str = "TP") -> dict:
        return {"orderId": f"RED-{int(time.time()*1000)}", "symbol": symbol, "side": side, "qty": qty, "price": price, "kind": kind, "role": role}
    
    def place_reduce_only_stop(self, symbol: str, side: str, qty: float, stop_price: float, role: str = "SL") -> dict:
        return {"orderId": f"STP-{int(time.time()*1000)}", "symbol": symbol, "side": side, "qty": qty, "stop_price": stop_price, "role": role}

    def get_open_orders(self, symbol: str) -> list[dict]:
        return [o for o in self.orders.get(symbol, []) if not o.get("canceled") and not o.get("filled")]
    
    def list_open_orders(self, symbol: str) -> list[dict]:
        """Алиас для get_open_orders для совместимости с reconciler."""
        return self.get_open_orders(symbol)
    
    def fetch_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[list]:
        """Возвращает синтетические OHLCV данные для тестирования."""
        import pandas as pd
        from datetime import datetime, timedelta
        
        # Создаем синтетические данные
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=limit)
        
        # Генерируем временные метки
        timestamps = pd.date_range(start_time, end_time, freq='1H')[:-1]
        
        # Базовые цены для разных символов
        base_prices = {
            'ADAUSDT': 0.45,
            'DOGEUSDT': 0.08,
            'LTCUSDT': 65.0,
            'BTCUSDT': 45000.0
        }
        
        base_price = base_prices.get(symbol, 100.0)
        ohlcv_data = []
        
        for i, ts in enumerate(timestamps):
            # Простая синусоидальная модель цены
            price_factor = 1.0 + 0.1 * (i / len(timestamps)) + 0.05 * (i % 10) / 10
            price = base_price * price_factor
            
            # OHLCV данные
            open_price = price
            high_price = price * 1.02
            low_price = price * 0.98
            close_price = price * 1.01
            volume = 1000.0 + (i % 100) * 10
            
            ohlcv_data.append([
                int(ts.timestamp() * 1000),  # openTime
                open_price,                  # open
                high_price,                  # high
                low_price,                   # low
                close_price,                 # close
                volume,                      # volume
                int(ts.timestamp() * 1000) + 3600000,  # closeTime
                volume * close_price,        # quoteAssetVolume
                100,                         # count
                volume * 0.6,                # takerBuyBaseAssetVolume
                volume * close_price * 0.6,  # takerBuyQuoteAssetVolume
                "0"                          # ignore
            ])
        
        return ohlcv_data
