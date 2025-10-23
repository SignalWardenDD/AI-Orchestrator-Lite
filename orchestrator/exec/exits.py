# orchestrator/exec/exits.py
"""
Разместитель выходов из позиций.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from .broker import Broker
from .dummy_broker import DummyBroker

class ExitsPlacer:
    """Разместитель выходов из позиций."""
    
    def __init__(self, broker: Optional[Broker] = None):
        self.active_exits = {}
        self.broker = broker or DummyBroker()
    
    def place_reduce_only_stop(self, symbol: str, side: str, qty: float, stop_price: float, role: str = "SL") -> Optional[str]:
        """Размещает reduce-only стоп ордер."""
        try:
            result = self.broker.place_reduce_only_stop(symbol, side, qty, stop_price, role)
            if result and "orderId" in result:
                order_id = str(result["orderId"])
                if symbol not in self.active_exits:
                    self.active_exits[symbol] = {}
                self.active_exits[symbol][role] = {
                    "order_id": order_id,
                    "side": side,
                    "qty": qty,
                    "price": stop_price,
                    "role": role
                }
                return order_id
        except Exception as e:
            print(f"❌ Ошибка размещения reduce-only стоп ордера: {e}")
        return None
    
    def place_reduce_only_limit(self, symbol: str, side: str, qty: float, price: float, role: str = "TP") -> Optional[str]:
        """Размещает reduce-only лимитный ордер."""
        try:
            result = self.broker.place_reduce_only(symbol, side, qty, price, "TP", role)
            if result and "orderId" in result:
                order_id = str(result["orderId"])
                if symbol not in self.active_exits:
                    self.active_exits[symbol] = {}
                self.active_exits[symbol][role] = {
                    "order_id": order_id,
                    "side": side,
                    "qty": qty,
                    "price": price,
                    "role": role
                }
                return order_id
        except Exception as e:
            print(f"❌ Ошибка размещения reduce-only лимитного ордера: {e}")
        return None
    
    def place_exits(self, position: Dict[str, Any]) -> bool:
        """Размещает выходы из позиции."""
        try:
            symbol = position.get("symbol")
            side = position.get("side")
            qty = position.get("qty", 0.0)
            entry_price = position.get("entry_price", 0.0)
            sl_price = position.get("sl_price")
            tp_levels = position.get("tp_levels", [])
            
            if not all([symbol, side, qty, entry_price]):
                print(f"❌ Неполные данные позиции: {position}")
                return False
            
            # Размещаем Stop Loss
            if sl_price:
                sl_order_id = self.place_reduce_only_stop(symbol, side, qty, sl_price, "SL")
                if sl_order_id:
                    print(f"✅ Размещен SL: {symbol} {side} {qty} @ {sl_price}")
            
            # Размещаем Take Profit уровни
            for i, (tp_price, tp_qty) in enumerate(tp_levels, 1):
                tp_order_id = self.place_reduce_only_limit(symbol, side, tp_qty, tp_price, f"TP{i}")
                if tp_order_id:
                    print(f"✅ Размещен TP{i}: {symbol} {side} {tp_qty} @ {tp_price}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка размещения выходов: {e}")
            return False
    
    def cancel_exits(self, symbol: str) -> bool:
        """Отменяет выходы из позиции."""
        if symbol in self.active_exits:
            try:
                for role, exit_info in self.active_exits[symbol].items():
                    self.broker.cancel_order(symbol, exit_info["order_id"])
                    print(f"✅ Отменен {role} ордер: {symbol}")
                del self.active_exits[symbol]
                return True
            except Exception as e:
                print(f"❌ Ошибка отмены выходов: {e}")
        return False