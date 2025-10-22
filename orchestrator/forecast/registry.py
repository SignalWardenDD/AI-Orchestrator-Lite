from __future__ import annotations
from typing import List
from .lgbm_forecaster import LGBMForecaster
from ..utils.types import SignalCandidate, FirstHitForecast

# Глобальный реестр (по типам) — грузит модели офлайн.

class ForecastRegistry:
    def __init__(self):
        # TODO: реальная загрузка моделей из config/ml_forecast.yaml
        self.by_type = {
            "BRK": LGBMForecaster("BRK", model_registry={2: object(), 4: object(), 6: object(), 10: object()}),
            "PB":  LGBMForecaster("PB",  model_registry={2: object(), 4: object(), 6: object(), 10: object()}),
            "TRND":LGBMForecaster("TRND",model_registry={2: object(), 4: object(), 6: object(), 10: object()}),
            "BB":  LGBMForecaster("BB",  model_registry={2: object(), 4: object(), 6: object(), 10: object()}),
        }

    def forecast(self, candidates: List[SignalCandidate], horizons: List[int]) -> List[FirstHitForecast]:
        out: List[FirstHitForecast] = []
        for t, model in self.by_type.items():
            out.extend(model.predict_many(candidates, horizons))
        return out
