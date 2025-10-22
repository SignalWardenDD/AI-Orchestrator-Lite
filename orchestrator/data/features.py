from __future__ import annotations
from typing import List, Tuple
from math import isnan
from ..utils.types import Bar, FeatureRow

# Упрощённые чистые реализации без внешних зависимостей.

def atr14(bars: List[Bar]) -> List[float]:
    out: List[float] = []
    prev_close = None
    tr_vals: List[float] = []
    for b in bars:
        if prev_close is None:
            tr = b.high - b.low
        else:
            tr = max(b.high - b.low, abs(b.high - prev_close), abs(b.low - prev_close))
        tr_vals.append(tr)
        prev_close = b.close
        if len(tr_vals) < 14:
            out.append(sum(tr_vals) / len(tr_vals))
        else:
            out.append(sum(tr_vals[-14:]) / 14.0)
    return out


def ema(series: List[float], period: int) -> List[float]:
    if not series:
        return []
    k = 2.0 / (period + 1)
    out: List[float] = []
    ema_prev = series[0]
    for v in series:
        ema_prev = (v - ema_prev) * k + ema_prev
        out.append(ema_prev)
    return out


def sma(series: List[float], period: int) -> List[float]:
    out: List[float] = []
    acc = 0.0
    for i, v in enumerate(series):
        acc += v
        if i >= period:
            acc -= series[i - period]
        n = min(i + 1, period)
        out.append(acc / n)
    return out


def rsi(series: List[float], period: int) -> List[float]:
    if len(series) < 2:
        return [50.0] * len(series)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(series)):
        ch = series[i] - series[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_g = sma(gains[1:], period)
    avg_l = sma(losses[1:], period)
    out: List[float] = [50.0]
    for g, l in zip(avg_g, avg_l):
        if l == 0:
            out.append(100.0)
        else:
            rs = g / l
            out.append(100 - (100 / (1 + rs)))
    return out[:len(series)]


def stddev(series: List[float], period: int) -> List[float]:
    out: List[float] = []
    for i in range(len(series)):
        start = max(0, i - period + 1)
        win = series[start:i+1]
        m = sum(win) / len(win)
        var = sum((x - m) ** 2 for x in win) / len(win)
        out.append(var ** 0.5)
    return out


def bollinger(series: List[float], period: int = 20, mult: float = 2.0) -> Tuple[List[float], List[float], List[float], List[float]]:
    mid = sma(series, period)
    sd = stddev(series, period)
    up = [m + mult * s for m, s in zip(mid, sd)]
    low = [m - mult * s for m, s in zip(mid, sd)]
    # bandwidth = (up - low) / mid
    bw = []
    for m, u, l in zip(mid, up, low):
        if m == 0:
            bw.append(0.0)
        else:
            bw.append((u - l) / m)
    return mid, up, low, bw


def build_feature_rows(bars: List[Bar]) -> List[FeatureRow]:
    closes = [b.close for b in bars]
    a14 = atr14(bars)
    ema20v = ema(closes, 20)
    ema50v = ema(closes, 50)
    ema200v = ema(closes, 200)
    rsi2v = rsi(closes, 2)
    rsi14v = rsi(closes, 14)
    mid, up, low, bw = bollinger(closes, 20, 2.0)

    rows: List[FeatureRow] = []
    for i, b in enumerate(bars):
        atr = a14[i]
        ema20_i = ema20v[i]
        dist_atr = (abs(b.close - ema20_i) / atr) if atr > 0 else 0.0
        slope_mid = 0.0 if i == 0 else (mid[i] - mid[i-1])
        natr_pct = (atr / b.close * 100.0) if b.close > 0 else 0.0
        row: FeatureRow = {
            "ts": b.ts,
            "close": b.close,
            "atr14": atr,
            "natr14_pct": natr_pct,
            "ema20": ema20_i,
            "ema50": ema50v[i],
            "ema200": ema200v[i],
            "rsi2": rsi2v[i],
            "rsi14": rsi14v[i],
            "bb_mid": mid[i],
            "bb_up": up[i],
            "bb_low": low[i],
            "bb_bw": bw[i],
            "dist_to_ema20_atr": dist_atr,
            "mid_slope": slope_mid,
        }
        rows.append(row)
    return rows
