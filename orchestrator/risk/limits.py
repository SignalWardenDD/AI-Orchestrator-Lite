# orchestrator/risk/limits.py
"""
Модуль для управления лимитами позиций и блокировки повторных входов.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

def can_open_new_position(state, symbol: str, cfg: Dict[str, Any]) -> bool:
    """
    Проверяет, можно ли открыть новую позицию.
    
    Args:
        state: Состояние системы
        symbol: Символ
        cfg: Конфигурация риска
    
    Returns:
        True если можно открыть позицию, False иначе
    """
    # Проверяем глобальный лимит позиций
    max_global = cfg.get("max_open_positions_global", 4)
    if state.open_positions_count() >= max_global:
        return False
    
    # Проверяем, есть ли уже открытая позиция по символу
    if state.has_open_position(symbol):
        return False
    
    # Защита от гонки с отложенными ордерами на тот же символ
    if state.pending_entry_for(symbol):
        return False
    
    return True

def check_position_limits(state, symbol: str, cfg: Dict[str, Any]) -> tuple[bool, str]:
    """
    Проверяет лимиты позиций и возвращает результат с причиной.
    
    Returns:
        (can_open, reason)
    """
    # Глобальный лимит
    max_global = cfg.get("max_open_positions_global", 4)
    if state.open_positions_count() >= max_global:
        return False, f"Global position limit reached ({max_global})"
    
    # Лимит на символ
    if state.has_open_position(symbol):
        return False, f"Position already open for {symbol}"
    
    # Отложенные ордера
    if state.pending_entry_for(symbol):
        return False, f"Pending entry order for {symbol}"
    
    return True, "OK"

def get_available_slots(state, cfg: Dict[str, Any]) -> int:
    """
    Возвращает количество доступных слотов для новых позиций.
    """
    max_global = cfg.get("max_open_positions_global", 4)
    current = state.open_positions_count()
    return max(0, max_global - current)

class DailyLossGuard:
    """Страж дневных потерь."""
    
    def __init__(self, daily_limit: float):
        self.daily_limit = daily_limit
        self.daily_pnl = 0.0
    
    def check(self, current_pnl: float) -> bool:
        """Проверяет дневные потери."""
        return current_pnl >= self.daily_limit
    
    def update_pnl(self, pnl: float):
        """Обновляет дневной PnL."""
        self.daily_pnl += pnl

class WeeklySoftLimiter:
    """Мягкий недельный лимитер."""
    
    def __init__(self, max_negative_days: int):
        self.max_negative_days = max_negative_days
        self.negative_days = 0
    
    def check(self, daily_pnl: float) -> bool:
        """Проверяет недельные лимиты."""
        if daily_pnl < 0:
            self.negative_days += 1
        else:
            self.negative_days = 0
        
        return self.negative_days < self.max_negative_days