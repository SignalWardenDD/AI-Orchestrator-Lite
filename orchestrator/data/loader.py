# orchestrator/data/loader.py
"""
Загрузчик данных для обучения per-signal моделей.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

def load_features_df(symbol: str) -> pd.DataFrame:
    """
    Загружает фичи для символа.
    Ожидается файл data/features/{symbol}.parquet с колонками фичей.
    """
    features_path = Path(f"data/features/{symbol}.parquet")
    if features_path.exists():
        return pd.read_parquet(features_path)
    
    # Fallback: создаем базовые фичи из OHLCV
    print(f"Warning: No features found for {symbol}, creating from OHLCV data")
    kline = load_kline_df(symbol)
    return _create_basic_features(kline)

def load_kline_df(symbol: str) -> pd.DataFrame:
    """
    Загружает OHLCV данные для символа.
    """
    # Пробуем разные варианты имен файлов
    possible_paths = [
        Path(f"data/raw/binance_futures/1h/{symbol}.csv"),
        Path(f"data/raw/binance_futures/1h/{symbol}_1h_*.csv"),
    ]
    
    # Ищем файлы с паттерном {symbol}_1h_*.csv
    import glob
    pattern_paths = glob.glob(f"data/raw/binance_futures/1h/{symbol}_1h_*.csv")
    
    for path_str in pattern_paths:
        path = Path(path_str)
        if path.exists():
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            return df
    
    # Fallback: создаем фиктивные данные для тестирования
    print(f"Warning: No OHLCV data found for {symbol}, creating dummy data")
    return _create_dummy_ohlcv(symbol)

def _signals_path(symbol: str) -> Path:
    return Path("data/signals") / f"{symbol}.parquet"

def load_signal_marks_df(symbol: str) -> pd.DataFrame:
    """
    Загружает кэшированные метки сигналов для symbol.
    Если файла нет — подсказывает, как его построить.
    """
    path = _signals_path(symbol)
    if not path.exists():
        raise FileNotFoundError(
            f"Signal marks not found for {symbol}: {path}\n"
            f"→ Сначала сгенерируй marks: python3 scripts/build_signal_marks.py --symbols {symbol}"
        )
    df = pd.read_parquet(path)
    # sanity-check
    need = {"BRK","PB","MR","BB"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"{symbol} marks file missing columns: {missing} in {path}")
    return df.sort_index()

def _create_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Создает базовые фичи из OHLCV данных."""
    from ..utils.mathx import natr, ewma, zscore, pct_change_safe
    
    features = pd.DataFrame(index=df.index)
    
    # Returns
    features["ret_1"] = pct_change_safe(df["close"], 1)
    features["ret_3"] = pct_change_safe(df["close"], 3)
    features["ret_6"] = pct_change_safe(df["close"], 6)
    
    # EMAs
    features["ema20"] = ewma(df["close"], 20)
    features["ema50"] = ewma(df["close"], 50)
    features["ema200"] = ewma(df["close"], 200)
    features["ema20_slope"] = pct_change_safe(features["ema20"], 1)
    
    # Volatility
    features["natr14"] = natr(df["high"], df["low"], df["close"], 14)
    features["rng_1"] = (df["high"] - df["low"]) / df["close"]
    features["rng_3"] = features["rng_1"].rolling(3).mean()
    
    # Z-score
    features["z_close_50"] = zscore(df["close"] - features["ema50"], window=50)
    
    # Lags
    for k in (1, 2, 3):
        features[f"ret_1_lag{k}"] = features["ret_1"].shift(k)
        features[f"rng_1_lag{k}"] = features["rng_1"].shift(k)
    
    return features.dropna()

def _create_dummy_ohlcv(symbol: str) -> pd.DataFrame:
    """Создает фиктивные OHLCV данные для тестирования."""
    import pandas as pd
    import numpy as np
    
    # Создаем временной ряд
    dates = pd.date_range('2023-01-01', periods=1000, freq='H')
    np.random.seed(42)
    
    # Простая модель цены с трендом и шумом
    trend = np.linspace(100, 200, len(dates))
    noise = np.random.randn(len(dates)) * 5
    prices = trend + noise
    
    df = pd.DataFrame({
        'open': prices + np.random.randn(len(dates)) * 0.5,
        'high': prices + np.abs(np.random.randn(len(dates)) * 2),
        'low': prices - np.abs(np.random.randn(len(dates)) * 2),
        'close': prices,
        'volume': np.random.randint(1000, 10000, len(dates))
    }, index=dates)
    
    return df

def _create_dummy_marks(df: pd.DataFrame) -> pd.DataFrame:
    """Создает фиктивные метки сигналов для тестирования."""
    marks = pd.DataFrame(index=df.index)
    
    # Создаем случайные метки с низкой частотой
    np.random.seed(42)
    for signal in ["BRK", "PB", "MR", "BB"]:
        marks[signal] = (np.random.random(len(df)) < 0.05).astype(int)
    
    return marks
