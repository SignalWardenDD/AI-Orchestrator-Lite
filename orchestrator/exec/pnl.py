# orchestrator/exec/pnl.py
"""
Модуль для вычисления PnL позиций.
"""

from __future__ import annotations
from typing import Literal

def unrealized_pnl_usd(entry_price: float, current_price: float, qty: float, side: Literal["LONG", "SHORT"]) -> float:
    """
    Вычисляет нереализованный PnL позиции в USD.
    
    Args:
        entry_price: Цена входа
        current_price: Текущая цена
        qty: Количество
        side: Направление позиции
    
    Returns:
        PnL в USD (положительный = прибыль, отрицательный = убыток)
    """
    if side.upper() == "LONG":
        return (current_price - entry_price) * qty
    else:  # SHORT
        return (entry_price - current_price) * qty

def compute_price_for_pnl(entry_price: float, qty: float, side: Literal["LONG", "SHORT"], pnl_usd: float) -> float:
    """
    Возвращает цену, при которой PnL позиции (по qty) составит pnl_usd.
    
    PnL = (price - entry) * qty * dir; dir=+1 для LONG, -1 для SHORT
    => price = entry + pnl_usd / (qty * dir)
    
    Args:
        entry_price: Цена входа
        qty: Количество
        side: Направление позиции
        pnl_usd: Желаемый PnL в USD
    
    Returns:
        Цена, при которой PnL составит pnl_usd
    """
    if side.upper() == "LONG":
        return entry_price + (pnl_usd / qty)
    else:  # SHORT
        return entry_price - (pnl_usd / qty)
