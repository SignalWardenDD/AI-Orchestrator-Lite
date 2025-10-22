# forecast/labeling.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Literal, Tuple, Optional
import numpy as np
import pandas as pd


LabelType = Literal["binary_hit", "trinary", "direction", "regression"]


@dataclass
class HorizonSpec:
    """Label horizon and barriers, all in price terms relative to entry."""
    horizon_bars: int = 24          # e.g., 24 bars on 1h -> 1 day
    tp_mult_atr: float = 2.0
    sl_mult_atr: float = 2.0


def make_future_returns(close: pd.Series, horizon: int) -> pd.Series:
    """
    Simple forward return (close[t+h] / close[t] - 1).
    """
    fwd = close.shift(-horizon) / close - 1.0
    return fwd


def event_outcome_first_hit(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr: pd.Series,
    horizon_bars: int,
    tp_mult_atr: float,
    sl_mult_atr: float,
    side: Literal["LONG", "SHORT"] = "LONG",
) -> pd.Series:
    """
    Returns +1 if TP first, -1 if SL first, 0 if neither within horizon.
    For SHORT, TP/SL sides are inverted.
    """
    # Precompute absolute TP/SL distances in price
    tp_dist = atr * tp_mult_atr
    sl_dist = atr * sl_mult_atr

    out = pd.Series(index=close.index, dtype=float)

    for t in range(len(close)):
        c0 = close.iloc[t]
        if np.isnan(c0):
            out.iloc[t] = np.nan
            continue

        t_end = min(t + horizon_bars, len(close) - 1)
        # price barriers:
        if side == "LONG":
            tp_price = c0 * (1.0 + tp_dist.iloc[t] / c0)
            sl_price = c0 * (1.0 - sl_dist.iloc[t] / c0)
            # iterate bar-by-bar until hit:
            hit = 0.0
            for k in range(t + 1, t_end + 1):
                if low.iloc[k] <= sl_price:
                    hit = -1.0
                    break
                if high.iloc[k] >= tp_price:
                    hit = +1.0
                    break
            out.iloc[t] = hit
        else:  # SHORT
            tp_price = c0 * (1.0 - tp_dist.iloc[t] / c0)
            sl_price = c0 * (1.0 + sl_dist.iloc[t] / c0)
            hit = 0.0
            for k in range(t + 1, t_end + 1):
                if high.iloc[k] >= sl_price:
                    hit = -1.0
                    break
                if low.iloc[k] <= tp_price:
                    hit = +1.0
                    break
            out.iloc[t] = hit

    return out


def event_outcome_first_hit_open_entry(
    high: pd.Series,
    low: pd.Series,
    open_: pd.Series,
    atr: pd.Series,
    horizon_bars: int,
    tp_mult_atr: float,
    sl_mult_atr: float,
    side: Literal["LONG", "SHORT"] = "LONG",
) -> pd.Series:
    """
    Как event_outcome_first_hit, но вход на OPEN[t], путь оценивается с бара t (включая t),
    т.е. моделируем мгновенный вход. ВАЖНО: фичи для этого примера ДОЛЖНЫ быть сдвинуты на t-1.
    """
    out = pd.Series(index=open_.index, dtype=float)
    for t in range(len(open_)):
        o0 = open_.iloc[t]
        if np.isnan(o0):
            out.iloc[t] = np.nan
            continue
        t_end = min(t + horizon_bars, len(open_) - 1)
        tp_dist = atr.iloc[t] * tp_mult_atr
        sl_dist = atr.iloc[t] * sl_mult_atr

        if side == "LONG":
            tp_price = o0 * (1.0 + tp_dist / max(o0, 1e-12))
            sl_price = o0 * (1.0 - sl_dist / max(o0, 1e-12))
            hit = 0.0
            for k in range(t, t_end + 1):  # включаем бар t
                if low.iloc[k] <= sl_price:
                    hit = -1.0
                    break
                if high.iloc[k] >= tp_price:
                    hit = +1.0
                    break
            out.iloc[t] = hit
        else:
            tp_price = o0 * (1.0 - tp_dist / max(o0, 1e-12))
            sl_price = o0 * (1.0 + sl_dist / max(o0, 1e-12))
            hit = 0.0
            for k in range(t, t_end + 1):
                if high.iloc[k] >= sl_price:
                    hit = -1.0
                    break
                if low.iloc[k] <= tp_price:
                    hit = +1.0
                    break
            out.iloc[t] = hit
    return out


def build_labels_open_entry(
    ohlc: pd.DataFrame,
    atr_series: pd.Series,
    horizon: HorizonSpec,
    task: LabelType = "binary_hit",
    side: Literal["LONG", "SHORT"] = "LONG",
) -> pd.Series:
    """
    Разметка под мгновенный вход на OPEN[t] и путь с t..t+h. Для binary_hit возвращает {-1,0,+1}.
    Для direction/trinary/regression — как раньше (но имей в виду, что фичи сдвигаются снаружи).
    """
    if task == "binary_hit":
        return event_outcome_first_hit_open_entry(
            ohlc["high"], ohlc["low"], ohlc["open"], atr_series,
            horizon_bars=horizon.horizon_bars,
            tp_mult_atr=horizon.tp_mult_atr,
            sl_mult_atr=horizon.sl_mult_atr,
            side=side
        )
    # Остальные задачи можно оставить как есть:
    return build_labels(ohlc, atr_series, horizon, task=task, side=side)


def label_direction(close: pd.Series, horizon_bars: int) -> pd.Series:
    """Direction label: sign of forward return."""
    fwd = make_future_returns(close, horizon_bars)
    return np.sign(fwd).astype(float)


def label_regression(close: pd.Series, horizon_bars: int) -> pd.Series:
    """Regression target: forward return value."""
    return make_future_returns(close, horizon_bars)


def label_trinary(close: pd.Series, horizon_bars: int, deadzone: float = 0.001) -> pd.Series:
    """
    -1, 0, +1 based on forward return with deadzone around 0.
    """
    fwd = make_future_returns(close, horizon_bars)
    out = pd.Series(index=close.index, dtype=float)
    out[fwd > deadzone] = +1.0
    out[fwd < -deadzone] = -1.0
    out[(fwd <= deadzone) & (fwd >= -deadzone)] = 0.0
    return out


def build_labels(
    ohlc: pd.DataFrame,
    atr_series: pd.Series,
    horizon: HorizonSpec,
    task: LabelType = "binary_hit",
    side: Literal["LONG", "SHORT"] = "LONG",
) -> pd.Series:
    """
    General label builder used by training scripts.
    ohlc must contain: ["open","high","low","close"].
    """
    close = ohlc["close"]

    if task == "binary_hit":
        return event_outcome_first_hit(
            ohlc["high"], ohlc["low"], close, atr_series,
            horizon_bars=horizon.horizon_bars,
            tp_mult_atr=horizon.tp_mult_atr,
            sl_mult_atr=horizon.sl_mult_atr,
            side=side
        )
    elif task == "direction":
        return label_direction(close, horizon.horizon_bars)
    elif task == "trinary":
        return label_trinary(close, horizon.horizon_bars)
    elif task == "regression":
        return label_regression(close, horizon.horizon_bars)
    else:
        raise ValueError(f"Unknown task: {task}")