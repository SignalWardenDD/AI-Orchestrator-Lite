# forecast/features_builder.py
"""
Унифицированный сборщик признаков для ML моделей.
Создает признаки из SignalCandidate и OHLC данных в том же формате, что и при обучении.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from ..utils.types import SignalCandidate
from ..utils.mathx import natr, atr, ewma, zscore, pct_change_safe


class FeaturesBuilder:
    """
    Сборщик признаков для ML моделей.
    Создает признаки в том же формате, что и при обучении в train_forecasters.py.
    """
    
    def __init__(self):
        self.feature_names = [
            'ret_1', 'ret_3', 'ret_6',
            'ema20', 'ema50', 'ema200', 'ema20_slope',
            'natr14', 'rng_1', 'rng_3', 'z_close_50',
            'ret_1_lag1', 'ret_1_lag2', 'ret_1_lag3',
            'rng_1_lag1', 'rng_1_lag2', 'rng_1_lag3'
        ]
    
    def build_from_candidate(self, candidate: SignalCandidate, ohlc_data: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        Создание признаков из SignalCandidate.
        
        Args:
            candidate: Кандидат сигнала
            ohlc_data: OHLC данные (опционально, для полных признаков)
        
        Returns:
            Словарь признаков в формате {feature_name: value}
        """
        features = {}
        
        if ohlc_data is not None and not ohlc_data.empty:
            # Полные признаки из OHLC данных
            features.update(self._build_from_ohlc(ohlc_data, candidate.symbol))
        else:
            # Базовые признаки из кандидата (fallback)
            features.update(self._build_from_candidate_basic(candidate))
        
        # Добавляем символьный признак
        features[f'sym__{candidate.symbol}'] = 1.0
        
        # Заполняем отсутствующие признаки нулями
        for name in self.feature_names:
            if name not in features:
                features[name] = 0.0
        
        return features
    
    def _build_from_ohlc(self, ohlc_data: pd.DataFrame, symbol: str) -> Dict[str, float]:
        """Создание признаков из OHLC данных."""
        if len(ohlc_data) < 50:  # Минимум данных для расчета
            return self._build_fallback_features()
        
        try:
            close = ohlc_data['close']
            high = ohlc_data['high']
            low = ohlc_data['low']
            
            # Базовые признаки
            features = {
                'ret_1': pct_change_safe(close, 1).iloc[-1],
                'ret_3': pct_change_safe(close, 3).iloc[-1],
                'ret_6': pct_change_safe(close, 6).iloc[-1],
                'ema20': ewma(close, 20).iloc[-1],
                'ema50': ewma(close, 50).iloc[-1],
                'ema200': ewma(close, 200).iloc[-1],
                'natr14': natr(high, low, close, 14).iloc[-1],
            }
            
            # EMA20 slope
            ema20_series = ewma(close, 20)
            features['ema20_slope'] = pct_change_safe(ema20_series, 1).iloc[-1]
            
            # Range features
            rng_1 = (high - low) / close.replace(0.0, np.nan)
            features['rng_1'] = rng_1.iloc[-1]
            features['rng_3'] = rng_1.rolling(3).mean().iloc[-1]
            
            # Z-score vs EMA50
            features['z_close_50'] = zscore(close - features['ema50'], window=50).iloc[-1]
            
            # Lag features
            ret_1_series = pct_change_safe(close, 1)
            features['ret_1_lag1'] = ret_1_series.shift(1).iloc[-1]
            features['ret_1_lag2'] = ret_1_series.shift(2).iloc[-1]
            features['ret_1_lag3'] = ret_1_series.shift(3).iloc[-1]
            
            features['rng_1_lag1'] = rng_1.shift(1).iloc[-1]
            features['rng_1_lag2'] = rng_1.shift(2).iloc[-1]
            features['rng_1_lag3'] = rng_1.shift(3).iloc[-1]
            
            # Заполнение NaN значений
            for key, value in features.items():
                if pd.isna(value) or np.isinf(value):
                    features[key] = 0.0
            
            return features
            
        except Exception as e:
            print(f"⚠️  Ошибка создания признаков из OHLC: {e}")
            return self._build_fallback_features()
    
    def _build_from_candidate_basic(self, candidate: SignalCandidate) -> Dict[str, float]:
        """Создание базовых признаков из кандидата (fallback)."""
        return {
            'ret_1': 0.0,
            'ret_3': 0.0,
            'ret_6': 0.0,
            'ema20': candidate.ema20,
            'ema50': candidate.ema20,  # fallback
            'ema200': candidate.ema20,  # fallback
            'ema20_slope': 0.0,
            'natr14': candidate.atr / candidate.entry_price * 100,
            'rng_1': 0.0,
            'rng_3': 0.0,
            'z_close_50': 0.0,
            'ret_1_lag1': 0.0,
            'ret_1_lag2': 0.0,
            'ret_1_lag3': 0.0,
            'rng_1_lag1': 0.0,
            'rng_1_lag2': 0.0,
            'rng_1_lag3': 0.0,
        }
    
    def _build_fallback_features(self) -> Dict[str, float]:
        """Fallback признаки при ошибке."""
        return {name: 0.0 for name in self.feature_names}
    
    def get_feature_names(self) -> List[str]:
        """Возвращает список имен признаков."""
        return self.feature_names.copy()


# Глобальный экземпляр для удобства
_features_builder = FeaturesBuilder()


def build_features_for_candidate(candidate: SignalCandidate, ohlc_data: Optional[pd.DataFrame] = None) -> Dict[str, float]:
    """
    Удобная функция для создания признаков из кандидата.
    
    Args:
        candidate: Кандидат сигнала
        ohlc_data: OHLC данные (опционально)
    
    Returns:
        Словарь признаков
    """
    return _features_builder.build_from_candidate(candidate, ohlc_data)


def get_standard_feature_names() -> List[str]:
    """Возвращает стандартные имена признаков."""
    return _features_builder.get_feature_names()
