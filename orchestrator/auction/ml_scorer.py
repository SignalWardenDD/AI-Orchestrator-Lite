# auction/ml_scorer.py
"""
ML-адаптер для auction/scorer.py.
Добавляет использование обученных ML моделей в скоринг кандидатов.
Безопасно интегрируется с существующим кодом без его изменения.
"""

from __future__ import annotations
import os
import glob
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from ..utils.types import SignalCandidate, FirstHitForecast, ScoredCandidate
from ..forecast.lgbm_forecaster import Forecaster
from ..forecast.features_builder import build_features_for_candidate


class MLScorerAdapter:
    """
    Адаптер для интеграции ML моделей в скоринг.
    Автоматически загружает обученные модели и использует их для улучшения скоринга.
    """
    
    def __init__(self, models_dir: str = "forecast/models"):
        self.models_dir = models_dir
        self.forecasters: Dict[str, Dict[int, Forecaster]] = {}  # {type: {horizon: forecaster}}
        self._load_models()
    
    def _load_models(self):
        """Автоматическая загрузка всех доступных моделей."""
        if not os.path.exists(self.models_dir):
            print(f"⚠️  Директория моделей не найдена: {self.models_dir}")
            return
        
        # Поиск всех .joblib файлов
        pattern = os.path.join(self.models_dir, "*.joblib")
        model_files = glob.glob(pattern)
        
        for model_path in model_files:
            try:
                # Извлечение типа и горизонта из имени файла
                model_type, horizon = self._parse_model_path(model_path)
                if not model_type or not horizon:
                    continue
                
                # Загрузка модели
                forecaster = Forecaster(model_path)
                
                if model_type not in self.forecasters:
                    self.forecasters[model_type] = {}
                
                self.forecasters[model_type][horizon] = forecaster
                print(f"✅ Загружена ML модель: {model_type} H{horizon}")
                
            except Exception as e:
                print(f"❌ Ошибка загрузки модели {model_path}: {e}")
    
    def _parse_model_path(self, model_path: str) -> tuple[Optional[str], Optional[int]]:
        """Извлечение типа модели и горизонта из пути."""
        import re
        
        filename = os.path.basename(model_path)
        
        # Паттерны для разных типов моделей
        patterns = [
            r'(binary_hit|direction|trinary|regression)_(\w+)_H(\d+)\.joblib',
            r'(\w+)_(\w+)_H(\d+)\.joblib',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                task = match.group(1)
                symbol_part = match.group(2)
                horizon = int(match.group(3))
                
                # Определение типа сигнала по символам или задаче
                if 'ADAUSDT' in symbol_part or 'LTCUSDT' in symbol_part:
                    # Универсальная модель - определяем по задаче
                    if task == 'binary_hit':
                        return 'BRK', horizon  # По умолчанию для binary_hit
                    elif task == 'direction':
                        return 'TRND', horizon
                    elif task == 'trinary':
                        return 'PB', horizon
                    else:
                        return 'BB', horizon
                else:
                    # Специфичная модель
                    return task, horizon
        
        return None, None
    
    def get_ml_probability(self, candidate: SignalCandidate, horizon: int, ohlc_data: Optional[pd.DataFrame] = None) -> float:
        """
        Получение ML вероятности для кандидата.
        
        Args:
            candidate: Кандидат сигнала
            horizon: Горизонт прогноза
            ohlc_data: OHLC данные (опционально)
        
        Returns:
            Вероятность от 0 до 1, или 0.5 если модель недоступна
        """
        if candidate.type not in self.forecasters:
            return 0.5
        
        if horizon not in self.forecasters[candidate.type]:
            return 0.5
        
        try:
            forecaster = self.forecasters[candidate.type][horizon]
            
            # Создание признаков
            features = build_features_for_candidate(candidate, ohlc_data)
            
            # Получение вероятности
            probability = forecaster.predict_proba_row(features)
            
            return float(probability)
            
        except Exception as e:
            print(f"⚠️  Ошибка ML предсказания для {candidate.type} H{horizon}: {e}")
            return 0.5
    
    def enhance_score_with_ml(self, candidate: SignalCandidate, base_score: float, horizon: int, ohlc_data: Optional[pd.DataFrame] = None) -> float:
        """
        Улучшение базового скора с использованием ML вероятности.
        
        Args:
            candidate: Кандидат сигнала
            base_score: Базовый скор
            horizon: Горизонт прогноза
            ohlc_data: OHLC данные
        
        Returns:
            Улучшенный скор
        """
        ml_prob = self.get_ml_probability(candidate, horizon, ohlc_data)
        
        # Мягкое улучшение скора на основе ML вероятности
        # ML вероятность 0.5 = нейтрально, >0.5 = бонус, <0.5 = штраф
        ml_factor = 0.8 + 0.4 * ml_prob  # 0.8-1.2 диапазон
        
        enhanced_score = base_score * ml_factor
        
        return enhanced_score
    
    def has_model(self, candidate_type: str, horizon: int) -> bool:
        """Проверка наличия модели для типа и горизонта."""
        return (candidate_type in self.forecasters and 
                horizon in self.forecasters[candidate_type])
    
    def get_available_models(self) -> Dict[str, List[int]]:
        """Возвращает список доступных моделей."""
        return {model_type: list(horizons.keys()) 
                for model_type, horizons in self.forecasters.items()}


# Глобальный экземпляр для удобства
_ml_scorer = None


def get_ml_scorer(models_dir: str = "forecast/models") -> MLScorerAdapter:
    """Получение глобального экземпляра ML скорера."""
    global _ml_scorer
    if _ml_scorer is None:
        _ml_scorer = MLScorerAdapter(models_dir)
    return _ml_scorer


def enhance_score_with_ml(candidate: SignalCandidate, base_score: float, horizon: int, ohlc_data: Optional[pd.DataFrame] = None) -> float:
    """
    Удобная функция для улучшения скора с ML.
    
    Args:
        candidate: Кандидат сигнала
        base_score: Базовый скор
        horizon: Горизонт прогноза
        ohlc_data: OHLC данные
    
    Returns:
        Улучшенный скор
    """
    scorer = get_ml_scorer()
    return scorer.enhance_score_with_ml(candidate, base_score, horizon, ohlc_data)
