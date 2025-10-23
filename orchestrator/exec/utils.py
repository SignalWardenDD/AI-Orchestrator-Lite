# orchestrator/exec/utils.py
"""
Утилиты для модуля execution.
"""

from __future__ import annotations
from typing import Literal

def opposite(side: str) -> str:
    """
    Возвращает противоположную сторону для ордера.
    
    Args:
        side: "LONG" или "SHORT"
        
    Returns:
        "SELL" для LONG, "BUY" для SHORT
    """
    if side.upper() in ["LONG", "BUY"]:
        return "SELL"
    elif side.upper() in ["SHORT", "SELL"]:
        return "BUY"
    else:
        raise ValueError(f"Unknown side: {side}")

def tick_round(price: float, tick_size: float) -> float:
    """
    Округляет цену до ближайшего тика.
    
    Args:
        price: Цена для округления
        tick_size: Размер тика
        
    Returns:
        Округленная цена
    """
    if tick_size <= 0:
        return price
    # Округляем к ближайшему тику
    return round(price / tick_size) * tick_size
