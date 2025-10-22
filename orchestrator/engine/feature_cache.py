# engine/feature_cache.py
"""
Кэш признаков по символам для оптимизации производительности.
Избегает повторного расчета признаков для одного символа в рамках одного цикла.
"""

from __future__ import annotations
import time
from typing import Dict, Optional
import pandas as pd

from features.builder import build_features_for_candidate


class FeatureCache:
    """
    Кэш признаков для оптимизации производительности.
    Кэширует признаки по символам на определенное время.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._timestamps: Dict[str, float] = {}
    
    def get_features(self, symbol: str, ohlc_1h: pd.DataFrame) -> pd.DataFrame:
        """
        Получение признаков для символа.
        Если признаки есть в кэше и не устарели - возвращает из кэша.
        Иначе рассчитывает и кэширует.
        
        Args:
            symbol: Символ
            ohlc_1h: OHLC данные
        
        Returns:
            DataFrame с признаками
        """
        cache_key = f"{symbol}_{hash(str(ohlc_1h.index[-1]))}"
        current_time = time.time()
        
        # Проверяем кэш
        if cache_key in self._cache:
            if current_time - self._timestamps[cache_key] < self.ttl_seconds:
                return self._cache[cache_key]["features"]
        
        # Рассчитываем признаки
        features = build_features_for_candidate(ohlc_1h, symbol, include_symbol_onehot=True)
        
        # Кэшируем
        self._cache[cache_key] = {
            "features": features,
            "symbol": symbol,
            "ohlc_hash": hash(str(ohlc_1h.index[-1]))
        }
        self._timestamps[cache_key] = current_time
        
        return features
    
    def get_features_dict(self, symbol: str, ohlc_1h: pd.DataFrame) -> Dict[str, float]:
        """
        Получение признаков в виде словаря.
        
        Args:
            symbol: Символ
            ohlc_1h: OHLC данные
        
        Returns:
            Словарь признаков
        """
        features_df = self.get_features(symbol, ohlc_1h)
        row = features_df.iloc[0]
        return {k: float(row[k]) for k in features_df.columns}
    
    def clear_expired(self):
        """Очистка устаревших записей из кэша."""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self._timestamps.items()
            if current_time - timestamp >= self.ttl_seconds
        ]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
    
    def clear_all(self):
        """Полная очистка кэша."""
        self._cache.clear()
        self._timestamps.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Статистика кэша."""
        return {
            "total_entries": len(self._cache),
            "unique_symbols": len(set(entry["symbol"] for entry in self._cache.values())),
            "oldest_entry": min(self._timestamps.values()) if self._timestamps else 0,
            "newest_entry": max(self._timestamps.values()) if self._timestamps else 0
        }


# Глобальный экземпляр кэша
_feature_cache = None


def get_feature_cache(ttl_seconds: int = 300) -> FeatureCache:
    """Получение глобального экземпляра кэша признаков."""
    global _feature_cache
    if _feature_cache is None:
        _feature_cache = FeatureCache(ttl_seconds)
    return _feature_cache


def clear_feature_cache():
    """Очистка глобального кэша признаков."""
    global _feature_cache
    if _feature_cache:
        _feature_cache.clear_all()
