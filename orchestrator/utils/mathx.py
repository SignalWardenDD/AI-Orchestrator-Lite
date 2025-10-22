# utils/mathx.py
from __future__ import annotations
import math
from typing import Iterable, Tuple
import numpy as np
import pandas as pd


EPS = 1e-12


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Safe division for scalars."""
    return a / b if abs(b) > EPS else default


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp scalar x into [lo, hi]."""
    if lo > hi:
        lo, hi = hi, lo
    return max(lo, min(hi, x))


def rescale_0_1(x: pd.Series | np.ndarray) -> pd.Series:
    """Rescale to [0,1] with robust guard when constant."""
    s = pd.Series(x).astype(float)
    rng = s.max() - s.min()
    if rng <= EPS:
        return pd.Series(np.zeros_like(s), index=s.index)
    return (s - s.min()) / rng


def sigmoid(x: pd.Series | np.ndarray | float) -> pd.Series | float:
    """Numerically stable sigmoid."""
    if np.isscalar(x):
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        z = math.exp(x)
        return z / (1.0 + z)
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    pos = x >= 0
    neg = ~pos
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    ex = np.exp(x[neg])
    out[neg] = ex / (1.0 + ex)
    return pd.Series(out)


def zscore(s: pd.Series, window: int = 20, ddof: int = 0) -> pd.Series:
    """Rolling z-score."""
    mu = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std(ddof=ddof)
    return (s - mu) / (sd.replace(0.0, np.nan))


def ewma(s: pd.Series, span: int) -> pd.Series:
    """Exponentially weighted moving average, pandas-native."""
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range series."""
    prev_close = close.shift(1)
    a = (high - low).abs()
    b = (high - prev_close).abs()
    c = (low - prev_close).abs()
    return pd.concat([a, b, c], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0/period, adjust=False, min_periods=period).mean()


def natr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Normalized ATR in percent (0..100)."""
    a = atr(high, low, close, period=period)
    return (a / close.replace(0.0, np.nan)).abs() * 100.0


def drawdown(equity: pd.Series) -> pd.Series:
    """Drawdown series (fractional, negative values)."""
    peak = equity.cummax()
    return (equity / peak) - 1.0


def sharpe(returns: pd.Series, rf: float = 0.0, periods_per_year: int = 365*24) -> float:
    """
    Annualized Sharpe for a returns series aligned to a fixed period
    (default assumes hourly; adjust periods_per_year as needed).
    """
    r = returns.dropna()
    if r.empty:
        return 0.0
    excess = r - rf / periods_per_year
    mu = excess.mean()
    sd = excess.std(ddof=1)
    if sd <= EPS:
        return 0.0
    return (mu / sd) * math.sqrt(periods_per_year)


def rolling_corr(a: pd.Series, b: pd.Series, window: int = 20) -> pd.Series:
    """Rolling Pearson correlation."""
    return a.rolling(window, min_periods=window).corr(b)


def pct_change_safe(s: pd.Series, periods: int = 1) -> pd.Series:
    """Safe pct change that avoids division by zero."""
    base = s.shift(periods)
    return (s - base) / base.replace(0.0, np.nan)