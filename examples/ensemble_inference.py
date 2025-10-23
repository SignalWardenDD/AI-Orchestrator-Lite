# examples/ensemble_inference.py
"""
Пример использования ансамбля H12+H24 в рантайме.
Интеграция с auction/scorer.py для модификации EV.
"""

from __future__ import annotations
import yaml
import pandas as pd
from typing import Dict, Any
from forecast.lgbm_forecaster import Forecaster

class EnsembleForecaster:
    """Ансамбль H12+H24 для групп A и B."""
    
    def __init__(self, config_path: str = "config/models.yaml"):
        with open(config_path) as f:
            self.mcfg = yaml.safe_load(f)["ml"]
        
        # Веса ансамбля
        self.w12 = self.mcfg["ensemble"]["weights"]["H12"]
        self.w24 = self.mcfg["ensemble"]["weights"]["H24"]
        
        # Группы
        A = self.mcfg["models"]["A_group"]
        B = self.mcfg["models"]["B_group"]
        
        # Инициализация моделей
        self.A12 = Forecaster(A["H12"]["path"], calibrator_prefer=A["H12"]["calibrator_prefer"])
        self.A24 = Forecaster(A["H24"]["path"], calibrator_prefer=A["H24"]["calibrator_prefer"])
        self.B12 = Forecaster(B["H12"]["path"], calibrator_prefer=B["H12"]["calibrator_prefer"])
        self.B24 = Forecaster(B["H24"]["path"], calibrator_prefer=B["H24"]["calibrator_prefer"])
        
        # Символы группы A
        self.A_SET = {"ADAUSDT", "HBARUSDT", "LTCUSDT"}
    
    def predict_proba_ensemble(self, features_df: pd.DataFrame, symbol: str) -> float:
        """
        Предсказание ансамбля H12+H24 для символа.
        
        Args:
            features_df: DataFrame с фичами
            symbol: Торговый символ
            
        Returns:
            Вероятность (0..1) от ансамбля
        """
        if symbol in self.A_SET:
            # Группа A
            p12 = float(self.A12.predict_proba_df(features_df).iloc[0])
            p24 = float(self.A24.predict_proba_df(features_df).iloc[0])
        else:
            # Группа B
            p12 = float(self.B12.predict_proba_df(features_df).iloc[0])
            p24 = float(self.B24.predict_proba_df(features_df).iloc[0])
        
        # Взвешенное среднее
        return self.w12 * p12 + self.w24 * p24
    
    def get_ensemble_weights(self) -> Dict[str, float]:
        """Возвращает веса ансамбля."""
        return {"H12": self.w12, "H24": self.w24}


# Пример интеграции в auction/scorer.py
def enhanced_score_candidates_with_ensemble(
    candidates: list,
    ensemble_forecaster: EnsembleForecaster,
    base_score_func,  # Оригинальная функция скоринга
    **kwargs
) -> list:
    """
    Улучшенный скоринг с ансамблем ML.
    
    Args:
        candidates: Список кандидатов на торговлю
        ensemble_forecaster: Ансамбль H12+H24
        base_score_func: Базовая функция скоринга
        **kwargs: Дополнительные параметры
        
    Returns:
        Список кандидатов с обновленными скорами
    """
    # Получаем базовые скоры
    scored_candidates = base_score_func(candidates, **kwargs)
    
    for candidate in scored_candidates:
        try:
            # Строим фичи для кандидата
            features_df = build_features_for_candidate(candidate)
            
            # Получаем ML вероятность от ансамбля
            ml_prob = ensemble_forecaster.predict_proba_ensemble(
                features_df, candidate["symbol"]
            )
            
            # Модифицируем EV с помощью ML
            base_ev = candidate.get("expected_pnl", 0.0)
            ml_weight = 0.3  # Вес ML в финальном скоре
            ml_modulation = (ml_prob - 0.5) * 2.0  # [-1, +1]
            
            enhanced_ev = base_ev * (1.0 + ml_weight * ml_modulation)
            candidate["expected_pnl"] = enhanced_ev
            candidate["ml_prob"] = ml_prob
            candidate["ml_modulation"] = ml_modulation
            
        except Exception as e:
            # Фолбэк к базовому скору при ошибке ML
            candidate["ml_prob"] = 0.5
            candidate["ml_modulation"] = 0.0
            print(f"ML prediction failed for {candidate.get('symbol', 'unknown')}: {e}")
    
    return scored_candidates


# Пример использования
if __name__ == "__main__":
    # Инициализация ансамбля
    ensemble = EnsembleForecaster("config/models.yaml")
    
    # Пример фичей (в реальности из pipeline)
    sample_features = pd.DataFrame({
        "ret_1": [0.01],
        "ret_3": [0.02],
        "ema20": [100.0],
        "natr14": [2.5],
        # ... другие фичи
    })
    
    # Тест для разных символов
    for symbol in ["ADAUSDT", "PNUTUSDT"]:
        prob = ensemble.predict_proba_ensemble(sample_features, symbol)
        group = "A" if symbol in ensemble.A_SET else "B"
        print(f"{symbol} ({group}): ML prob = {prob:.3f}")
    
    print(f"Ensemble weights: {ensemble.get_ensemble_weights()}")
