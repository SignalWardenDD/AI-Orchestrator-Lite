# features/builder.py
from __future__ import annotations
from typing import Dict, Optional
import numpy as np
import pandas as pd

from utils.mathx import natr, ewma, zscore, pct_change_safe, atr

MIN_BARS = 220  # достаточно для EMA200 и zscore(50)

def _base_features(ohlc: pd.DataFrame) -> pd.DataFrame:
    close = ohlc["close"]
    high, low = ohlc["high"], ohlc["low"]

    feat = pd.DataFrame(index=ohlc.index)
    feat["ret_1"]       = pct_change_safe(close, 1)
    feat["ret_3"]       = pct_change_safe(close, 3)
    feat["ret_6"]       = pct_change_safe(close, 6)
    feat["ema20"]       = ewma(close, 20)
    feat["ema50"]       = ewma(close, 50)
    feat["ema200"]      = ewma(close, 200)
    feat["ema20_slope"] = pct_change_safe(feat["ema20"], 1)
    feat["natr14"]      = natr(high, low, close, 14)
    feat["rng_1"]       = (high - low) / close.replace(0.0, np.nan)
    feat["rng_3"]       = feat["rng_1"].rolling(3).mean()
    feat["z_close_50"]  = zscore(close - feat["ema50"], window=50)

    for k in (1, 2, 3):
        feat[f"ret_1_lag{k}"] = feat["ret_1"].shift(k)
        feat[f"rng_1_lag{k}"] = feat["rng_1"].shift(k)

    feat = feat.replace([np.inf, -np.inf], np.nan).dropna()
    return feat

def build_features_for_candidate(
    ohlc_1h: pd.DataFrame,
    symbol: str,
    include_symbol_onehot: bool = True,
) -> pd.DataFrame:
    """
    Возвращает DataFrame из 1 строки с актуальными фичами для кандидата.
    ohlc_1h: ожидаются колонки ['open','high','low','close'] и DatetimeIndex (UTC).
    """
    if ohlc_1h.shape[0] < MIN_BARS:
        # мягкий фолбэк — дозакачай данные заранее в ingest
        ohlc_1h = ohlc_1h.copy()

    feats = _base_features(ohlc_1h)
    if feats.empty:
        # если совсем нет, вернём нули по последней метке времени
        idx = ohlc_1h.index[-1:]
        feats = pd.DataFrame({c: [0.0] for c in [
            "ret_1","ret_3","ret_6","ema20","ema50","ema200","ema20_slope",
            "natr14","rng_1","rng_3","z_close_50",
            "ret_1_lag1","ret_1_lag2","ret_1_lag3","rng_1_lag1","rng_1_lag2","rng_1_lag3"
        ]}, index=idx)

    last = feats.tail(1).copy()
    if include_symbol_onehot:
        last[f"sym__{symbol}"] = 1.0

    # защита
    last = last.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return last

def build_features_dict(ohlc_1h: pd.DataFrame, symbol: str) -> Dict[str, float]:
    """Удобный helper: вернуть dict для Forecaster.predict_proba_row."""
    df = build_features_for_candidate(ohlc_1h, symbol)
    row = df.iloc[0]
    return {k: float(row[k]) for k in df.columns}
