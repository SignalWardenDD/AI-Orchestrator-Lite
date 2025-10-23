# orchestrator/guards/microstructure.py
"""
Микроструктурные гварды для предотвращения входов на экстремумах.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class Bar:
    """Структура бара для анализа."""
    open: float
    high: float
    low: float
    close: float

def microstructure_edge_guard(ctx, symbol: str, side: str) -> bool:
    """
    Блокирует входы на экстремумах свечей.
    
    True = БЛОКИРУЕМ сделку.
    Блокируем шорт на финальном участке «пролива» и лонг на финальном «памп-хайе».
    
    Args:
        ctx: Контекст с данными
        symbol: Символ
        side: Направление позиции
    
    Returns:
        True если нужно заблокировать сделку
    """
    try:
        # Получаем последний бар
        bar = ctx.last_bar[symbol]
        rsi2 = ctx.ind.rsi2[symbol]
        
        # Вычисляем характеристики бара
        rng = abs(bar.close - bar.open)
        body = abs(bar.close - bar.open)
        wick_down = bar.open - bar.low if bar.close > bar.open else bar.close - bar.low
        wick_up = bar.high - bar.close if bar.close > bar.open else bar.high - bar.open
        
        # «Красный пролив»: большой down-body, малая нижняя тень, экстремум RSI2
        dump_like = (
            (bar.close < bar.open) and 
            (body > 0.6 * rng) and 
            (wick_down < 0.15 * rng) and 
            (rsi2 <= 5)
        )
        
        # «Зелёный экстремум»: большой up-body, малая верхняя тень, RSI2 высокое
        pump_like = (
            (bar.close > bar.open) and 
            (body > 0.6 * rng) and 
            (wick_up < 0.15 * rng) and 
            (rsi2 >= 95)
        )
        
        # Блокируем входы на экстремумах
        if side == "SHORT" and dump_like:
            return True   # блок шорта на донышке
        if side == "LONG" and pump_like:
            return True   # блок лонга на вершине
        
        return False
        
    except Exception:
        # При ошибке не блокируем
        return False

def should_block_microstructure(ctx, symbol: str, side: str) -> tuple[bool, str]:
    """
    Проверяет микроструктурные блокеры.
    
    Returns:
        (should_block, reason)
    """
    if microstructure_edge_guard(ctx, symbol, side):
        return True, "Microstructure edge detected"
    
    return False, "OK"
