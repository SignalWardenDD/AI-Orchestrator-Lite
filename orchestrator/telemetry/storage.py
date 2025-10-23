from __future__ import annotations
import csv, os, json, time
from typing import Iterable

class CSVStore:
    def __init__(self, root: str = "./data"):
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def append_row(self, name: str, row: dict) -> None:
        path = os.path.join(self.root, f"{name}.csv")
        exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not exists:
                w.writeheader()
            w.writerow(row)

    def dump_json(self, name: str, payload: dict | list) -> None:
        path = os.path.join(self.root, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def timestamped(self, prefix: str) -> str:
        return f"{prefix}_{time.strftime('%Y-%m-%d')}"
