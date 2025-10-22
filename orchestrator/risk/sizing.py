from __future__ import annotations

def qty_from_notional(price: float, notional_usdt: float, step_size: float) -> float:
    raw = notional_usdt / max(price, 1e-9)
    # округление к шагу
    steps = int(raw / step_size)
    return max(steps * step_size, 0.0)
