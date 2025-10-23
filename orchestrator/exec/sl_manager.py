# orchestrator/exec/sl_manager.py
"""
Менеджер стоп-лоссов с поддержкой PnL-логики.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from .pnl import unrealized_pnl_usd, compute_price_for_pnl

class SLManager:
    """Менеджер стоп-лоссов."""
    
    def __init__(self, config):
        self.config = config
    
    def adjust_sl(self, position, unrealized_pnl):
        """Регулирует стоп-лосс позиции."""
        return maybe_adjust_sl(position, self.config)

def compute_price_for_pnl(entry_price: float, qty: float, side: str, pnl_usd: float) -> float:
    """
    Возвращает цену, при которой PnL позиции (по qty) составит pnl_usd.
    PnL = (price - entry) * qty * dir; dir=+1 для LONG, -1 для SHORT
    => price = entry + pnl_usd / (qty * dir)
    """
    if side.upper() == "LONG":
        return entry_price + (pnl_usd / qty)
    else:  # SHORT
        return entry_price - (pnl_usd / qty)

def _best_step(cfg, upnl_usd: float) -> Optional[float]:
    """
    Возвращает целевой PnL для SL (new_sl_pnl_usd) по максимальной достигнутой ступени.
    """
    # Получаем конфигурацию трейлинга
    trailing_config = getattr(cfg.exec, "pnl_trailing_usd", None)
    if not trailing_config:
        return None
    
    steps = getattr(trailing_config, "steps", [])
    if not steps:
        return None
    
    best = None
    for st in steps:
        if upnl_usd >= float(st["trigger_usd"]):
            best = float(st["new_sl_pnl_usd"])
    return best

def maybe_adjust_sl(ctx, position, tracker, cfg) -> bool:
    """Многоступенчатое подтягивание SL по $PnL с правилом 'никогда не ухудшать'."""
    sym = position.symbol
    side = position.side
    qty = position.qty
    entry = position.entry_price
    
    # Получаем текущую цену
    curr_price = ctx.market.last_price[sym]
    
    # Вычисляем текущий PnL
    upnl = unrealized_pnl_usd(entry, curr_price, qty, side)
    
    # Определяем целевую ступень SL
    target_pnl = _best_step(cfg, upnl)
    if target_pnl is None:
        return False
    
    # Цена, соответствующая целевому зафиксированному профиту
    new_sl_price = compute_price_for_pnl(entry, qty, side, pnl_usd=target_pnl)
    best = tracker.best_sl_price(sym)  # текущая «лучшая» (для LONG выше — лучше; для SHORT ниже — лучше)
    
    # Никогда не ухудшаем:
    if side.upper() == "LONG":
        if best == float("-inf") or new_sl_price > best:
            tracker.cancel_and_replace_sl(sym, new_sl_price)
            return True
    else:  # SHORT
        if best == float("-inf") or new_sl_price < best:
            tracker.cancel_and_replace_sl(sym, new_sl_price)
            return True
    
    return False

def compute_initial_sl(symbol: str, side: str, entry_price: float, atr: float, base_stop_usd: Optional[float] = None, sl_multiplier: float = 1.6) -> float:
    """
    Вычисляет начальный SL.
    
    Args:
        symbol: Символ
        side: Направление позиции
        entry_price: Цена входа
        atr: ATR для расчета
        base_stop_usd: Базовый SL в USD (приоритет)
        sl_multiplier: Мультипликатор ATR (fallback)
    
    Returns:
        Цена SL
    """
    if base_stop_usd is not None:
        # Используем PnL-таргет
        return compute_price_for_pnl(entry_price, 1.0, side, base_stop_usd)
    else:
        # Fallback к ATR-мультипликатору
        delta = sl_multiplier * atr
        return entry_price - delta if side == "LONG" else entry_price + delta