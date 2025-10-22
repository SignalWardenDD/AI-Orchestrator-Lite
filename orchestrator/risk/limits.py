from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict
import datetime as dt

@dataclass
class DailyLossGuard:
    limit_usdt: float  # отрицательное число, напр. -7.5

    def allowed(self, realized_today: float) -> bool:
        return realized_today > self.limit_usdt

@dataclass
class WeeklySoftLimiter:
    max_neg_days: int = 3
    spiky_symbols: set[str] = field(default_factory=set)
    # карта YYYY-WW -> count
    _neg_days: Dict[str, int] = field(default_factory=dict)

    def _week_key(self, d: dt.date) -> str:
        y, w, _ = d.isocalendar()
        return f"{y}-{w:02d}"

    def on_day_close(self, date: dt.date, day_pnl_usdt: float, spiky_today: set[str]):
        key = self._week_key(date)
        if day_pnl_usdt < 0:
            self._neg_days[key] = self._neg_days.get(key, 0) + 1
        self.spiky_symbols |= spiky_today

    def should_pause_spiky(self, date: dt.date) -> bool:
        key = self._week_key(date)
        return self._neg_days.get(key, 0) >= self.max_neg_days