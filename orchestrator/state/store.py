from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
from . import recon

@dataclass
class Position:
    symbol: str
    side: str
    qty_init: float          # исходное количество при входе
    qty: float               # текущий остаток (по последней сверке)
    entry_price: float
    ts_open: int
    tp1_done: bool = False
    tp2_done: bool = False
    tp3_done: bool = False
    tp_placed: bool = False
    sl_price: Optional[float] = None

@dataclass
class StateStore:
    positions: Dict[str, Position] = field(default_factory=dict)  # by symbol
    day_pnl_usdt: float = 0.0
    day_realized_usdt: float = 0.0
    paused_symbols: set[str] = field(default_factory=set)

    def get_slot_free(self, symbol: str) -> bool:
        return symbol not in self.positions

    def apply_fill_open(self, pos: Position) -> None:
        self.positions[pos.symbol] = pos

    def apply_close(self, symbol: str, realized_usdt: float) -> None:
        self.positions.pop(symbol, None)
        self.day_realized_usdt += realized_usdt

    def update_qty(self, symbol: str, new_qty: float) -> None:
        p = self.positions.get(symbol)
        if not p:
            return
        p.qty = new_qty

    def reset_day_stats(self) -> None:
        self.day_pnl_usdt = 0.0
        self.day_realized_usdt = 0.0
