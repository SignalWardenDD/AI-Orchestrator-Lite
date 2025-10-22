from __future__ import annotations
from typing import List, Tuple

# Утилиты для расчётов из feature-рядов (без тачки на сырые high/low).

def rolling_max(vals: List[float], n: int) -> List[float]:
    out = []
    for i in range(len(vals)):
        start = max(0, i - n + 1)
        out.append(max(vals[start:i+1]))
    return out

def rolling_min(vals: List[float], n: int) -> List[float]:
    out = []
    for i in range(len(vals)):
        start = max(0, i - n + 1)
        out.append(min(vals[start:i+1]))
    return out

def median(vals: List[float]) -> float:
    v = sorted(vals)
    m = len(v)
    if m == 0:
        return 0.0
    if m % 2 == 1:
        return v[m//2]
    return 0.5 * (v[m//2 - 1] + v[m//2])

def nr7_like(ranges: List[float], lookback: int = 7) -> List[bool]:
    """Флаг «узчайшего бара за N». Используем прокси‑range по BB ширине."""
    out = [False] * len(ranges)
    for i in range(len(ranges)):
        start = max(0, i - lookback + 1)
        win = ranges[start:i+1]
        if len(win) == lookback and win[-1] == min(win):
            out[i] = True
    return out
