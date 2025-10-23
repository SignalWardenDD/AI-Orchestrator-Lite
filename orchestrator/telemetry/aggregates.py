from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

@dataclass
class TradeOutcome:
    symbol: str
    type: str
    side: str
    pnl_usdt: float
    hit: str   # tp1|tp2|tp3|tp4|sl

@dataclass
class DayStats:
    total_trades: int = 0
    pnl_sum: float = 0.0
    wins: int = 0
    tp_counts: dict = field(default_factory=lambda: {"tp1":0,"tp2":0,"tp3":0,"tp4":0})

    def add(self, t: TradeOutcome):
        self.total_trades += 1
        self.pnl_sum += t.pnl_usdt
        if t.pnl_usdt > 0:
            self.wins += 1
        if t.hit in self.tp_counts:
            self.tp_counts[t.hit] += 1

    def pf(self) -> float:
        # gross profit factor на уровне дневных исходов (упрощённая версия)
        # В реальности суммируй абсолюты по win/loss
        return 1.0 if self.pnl_sum >= 0 else 0.0

    def wr(self) -> float:
        return (self.wins / self.total_trades) if self.total_trades else 0.0
