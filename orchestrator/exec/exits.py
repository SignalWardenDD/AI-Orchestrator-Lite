from __future__ import annotations
from typing import List, Tuple

class ExitsPlacer:
    """Ставит лесенку TP и один SL как reduce‑only LIMIT.
    Округление размеров/цены к шагам выполняется на уровне брокера (или здесь при необходимости).
    """
    def __init__(self, broker):
        self.broker = broker

    def place_tp_sl(self, symbol: str, side: str, tp_levels: List[Tuple[float, float]], sl_price: float) -> None:
        opp_side = "SELL" if side == "LONG" else "BUY"
        # TP‑лестница
        for price, qty in tp_levels:
            if qty <= 0:
                continue
            try:
                self.broker.place_reduce_only(
                    symbol=symbol,
                    side=opp_side,
                    qty=qty,
                    price=price,
                    kind="TP",
                )
            except Exception as e:
                # не падаем пайплайном из‑за одного уровня
                # логирование делает верхний слой (audit)
                pass
        # SL — один общий лимитный reduce‑only
        try:
            self.broker.place_reduce_only(
                symbol=symbol,
                side=opp_side,
                qty=sum(q for _, q in tp_levels),
                price=sl_price,
                kind="SL",
            )
        except Exception:
            pass
