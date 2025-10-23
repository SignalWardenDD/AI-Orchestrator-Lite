from __future__ import annotations

def qty_from_notional(price: float, notional_usdt: float, step_size: float) -> float:
    """
    Рассчитывает количество с правильным округлением к step_size.
    """
    if price <= 0 or step_size <= 0:
        return 0.0
    
    raw = notional_usdt / price
    # Округляем к ближайшему шагу с учетом точности
    steps = round(raw / step_size)
    result = steps * step_size
    
    # Дополнительная проверка для устранения погрешности float
    result = round(result / step_size) * step_size
    
    return max(result, 0.0)

def calculate_position_size(notional: float, leverage: float) -> float:
    """Рассчитывает размер позиции."""
    return notional * leverage
