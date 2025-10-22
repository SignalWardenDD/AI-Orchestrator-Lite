from __future__ import annotations
from typing import Iterable, List
from ..utils.types import SignalCandidate, FirstHitForecast

class Forecaster:
    type_name: str = "BASE"

    def predict_many(self, candidates: Iterable[SignalCandidate], horizons: List[int]) -> List[FirstHitForecast]:
        raise NotImplementedError
