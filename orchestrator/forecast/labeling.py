# orchestrator/forecast/labeling.py
"""
Функции создания лейблов для per-signal моделей.
"""

import pandas as pd
import numpy as np
from typing import Union

def make_binary_hit_labels(kline_df: pd.DataFrame, horizon: str) -> pd.Series:
    """
    Создает бинарные лейблы "hit TP раньше SL" для заданного горизонта.
    
    Args:
        kline_df: DataFrame с OHLCV данными
        horizon: Горизонт ("H12" или "H24")
        
    Returns:
        Series с лейблами 0/1, индекс по времени
    """
    # Конвертируем горизонт в количество баров
    horizon_bars = int(horizon[1:])  # H12 -> 12, H24 -> 24
    
    # Параметры TP/SL
    tp_mult_atr = 2.0
    sl_mult_atr = 2.0
    
    # Вычисляем ATR
    from ..utils.mathx import atr
    atr_series = atr(kline_df["high"], kline_df["low"], kline_df["close"], period=14)
    
    # Создаем лейблы для LONG позиций
    labels = _create_hit_labels(
        kline_df["high"], kline_df["low"], kline_df["close"],
        atr_series, horizon_bars, tp_mult_atr, sl_mult_atr, "LONG"
    )
    
    return labels

def _create_hit_labels(high: pd.Series, low: pd.Series, close: pd.Series, 
                      atr: pd.Series, horizon_bars: int, tp_mult: float, 
                      sl_mult: float, side: str) -> pd.Series:
    """
    Создает лейблы hit/miss для заданных параметров.
    """
    labels = pd.Series(0, index=close.index)
    
    for i in range(len(close) - horizon_bars):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] <= 0:
            continue
            
        entry_price = close.iloc[i]
        tp_price = entry_price + (tp_mult * atr.iloc[i]) if side == "LONG" else entry_price - (tp_mult * atr.iloc[i])
        sl_price = entry_price - (sl_mult * atr.iloc[i]) if side == "LONG" else entry_price + (sl_mult * atr.iloc[i])
        
        # Проверяем путь от i+1 до i+horizon_bars
        hit_tp = False
        hit_sl = False
        
        for j in range(i + 1, min(i + horizon_bars + 1, len(close))):
            if side == "LONG":
                if high.iloc[j] >= tp_price:
                    hit_tp = True
                    break
                if low.iloc[j] <= sl_price:
                    hit_sl = True
                    break
            else:  # SHORT
                if low.iloc[j] <= tp_price:
                    hit_tp = True
                    break
                if high.iloc[j] >= sl_price:
                    hit_sl = True
                    break
        
        # Лейбл: 1 если TP раньше SL, 0 иначе
        if hit_tp and not hit_sl:
            labels.iloc[i] = 1
        elif hit_sl and not hit_tp:
            labels.iloc[i] = 0
        else:
            labels.iloc[i] = 0  # Неопределенный случай
    
    return labels