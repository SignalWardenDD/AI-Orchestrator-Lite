from __future__ import annotations
from typing import Iterable
from .storage import CSVStore

class Reports:
    def __init__(self, store: CSVStore):
        self.store = store

    def daily_summary(self, stats: dict) -> None:
        name = self.store.timestamped("daily_report")
        self.store.dump_json(name, stats)

    def weekly_summary(self, stats: dict) -> None:
        name = self.store.timestamped("weekly_report")
        self.store.dump_json(name, stats)
