from __future__ import annotations
from typing import List, Optional
from ..utils.types import ScoredCandidate

SCORE_MIN_USDT = 0.12


def pick_winner(cands: List[ScoredCandidate]) -> Optional[ScoredCandidate]:
    eligible = [c for c in cands if c.score_usdt >= SCORE_MIN_USDT]
    if not eligible:
        return None
    # Группируем конфликтные (LONG vs SHORT одного символа)
    # Простая стратегия: выбрать глобальный максимум
    eligible.sort(key=lambda x: x.score_usdt, reverse=True)
    return eligible[0]
