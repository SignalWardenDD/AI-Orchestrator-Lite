from __future__ import annotations
from typing import List
from ..utils.types import SignalCandidate

class SignalProvider:
    type_name: str = "BASE"

    def generate(self, symbol: str, frows: list[dict]) -> List[SignalCandidate]:
        """На вход — последовательность feature-строк (1h). На выход — кандидаты.
        Реализация в наследниках.
        """
        raise NotImplementedError
