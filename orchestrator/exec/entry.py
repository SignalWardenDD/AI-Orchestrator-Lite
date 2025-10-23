# orchestrator/exec/entry.py
"""
Исполнитель входов в позиции.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from ..utils.types import ExecutionPlan
from .broker import Broker
from .dummy_broker import DummyBroker

class EntryExecutor:
    """Исполнитель входов в позиции."""
    
    def __init__(self, broker: Optional[Broker] = None):
        self.active_entries = {}
        self.broker = broker or DummyBroker()
    
    def place_postonly_limit(self, symbol: str, side: str, qty: float, price: float, role: str = "ENTRY") -> Optional[str]:
        """Размещает PostOnly лимитный ордер."""
        try:
            result = self.broker.place_postonly_limit(symbol, side, qty, price, role)
            if result and "orderId" in result:
                order_id = str(result["orderId"])
                self.active_entries[symbol] = {
                    "order_id": order_id,
                    "side": side,
                    "qty": qty,
                    "price": price,
                    "role": role
                }
                return order_id
        except Exception as e:
            print(f"❌ Ошибка размещения PostOnly ордера: {e}")
        return None
    
    def place_market(self, symbol: str, side: str, qty: float) -> Optional[str]:
        """Размещает рыночный ордер."""
        try:
            result = self.broker.place_market(symbol, side, qty)
            if result and "orderId" in result:
                return str(result["orderId"])
        except Exception as e:
            print(f"❌ Ошибка размещения рыночного ордера: {e}")
        return None
    
    def place_limit_and_track(self, plan: ExecutionPlan) -> Optional[str]:
        """Размещает лимитный ордер и начинает отслеживание."""
        try:
            # Размещаем PostOnly лимитный ордер
            order_id = self.place_postonly_limit(
                plan.symbol, 
                plan.side, 
                plan.qty, 
                plan.entry_limit, 
                "ENTRY"
            )
            
            if order_id:
                print(f"✅ Размещен PostOnly ордер: {plan.symbol} {plan.side} {plan.qty} @ {plan.entry_limit}")
                return order_id
            else:
                print(f"❌ Не удалось разместить PostOnly ордер для {plan.symbol}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка в place_limit_and_track: {e}")
            return None
    
    def cancel_entry(self, symbol: str) -> bool:
        """Отменяет вход в позицию."""
        if symbol in self.active_entries:
            entry = self.active_entries[symbol]
            try:
                self.broker.cancel_order(symbol, entry["order_id"])
                del self.active_entries[symbol]
                print(f"✅ Отменен ордер входа: {symbol}")
                return True
            except Exception as e:
                print(f"❌ Ошибка отмены ордера: {e}")
        return False