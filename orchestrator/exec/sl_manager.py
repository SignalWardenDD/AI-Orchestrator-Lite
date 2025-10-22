from __future__ import annotations
from typing import Optional

class SLManager:
    """Управление стопом: перенос в денежный BE и подъём после TP2/TP3.
    Предполагается, что текущая позиция и исходный entry доступны из брокера или StateStore.
    """
    def __init__(self, broker, fee_pct: float = 0.0008):
        self.broker = broker
        self.fee_pct = fee_pct

    def _calc_be_price(self, side: str, entry_price: float, be_usdt: float) -> float:
        fee_adj = entry_price * (2 * self.fee_pct)
        return (entry_price + fee_adj + be_usdt) if side == "LONG" else (entry_price - fee_adj - be_usdt)

    def move_to_be(self, symbol: str, side: str, entry_price: float, be_usdt: float, total_qty: float) -> Optional[float]:
        """Перенос SL в безубыток (денежный) — возвращает новую цену SL, если выставлен.
        SL выставляется reduce‑only лимитом на весь остаток позиции (total_qty).
        """
        new_sl = self._calc_be_price(side, entry_price, be_usdt)
        opp_side = "SELL" if side == "LONG" else "BUY"
        try:
            self.broker.place_reduce_only(symbol, opp_side, total_qty, new_sl, kind="SL")
            return new_sl
        except Exception:
            return None

    def raise_after_tp(self, symbol: str, side: str, current_entry: float, add_usdt: float, total_qty: float) -> Optional[float]:
        """Подъём SL в деньгах на add_usdt от entry."""
        return self.move_to_be(symbol, side, current_entry, add_usdt, total_qty)
