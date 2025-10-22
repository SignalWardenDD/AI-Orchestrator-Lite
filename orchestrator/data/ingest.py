from __future__ import annotations
from typing import List, Dict, Optional, Any
from ..utils.types import Bar

# Глобальная ссылка на источник данных (Broker) для простоты интеграции
_BROKER = None


def set_data_source(broker) -> None:
    global _BROKER
    _BROKER = broker


def _ensure_broker():
    if _BROKER is None:
        raise RuntimeError("Data ingest broker is not set. Call set_data_source(broker) at app start.")


def _klines_to_bars(klines: list[list[Any]]) -> List[Bar]:
    bars: List[Bar] = []
    for k in klines:
        # Binance futures klines schema:
        # [ openTime, open, high, low, close, volume, closeTime, ... ]
        ts = int(k[0])
        o = float(k[1]); h = float(k[2]); l = float(k[3]); c = float(k[4]); v = float(k[5])
        bars.append(Bar(ts=ts, open=o, high=h, low=l, close=c, volume=v))
    return bars


def fetch_ohlcv_1h(symbol: str, limit: int = 400) -> List[Bar]:
    _ensure_broker()
    kl = _BROKER.fetch_ohlcv(symbol, interval="1h", limit=limit)
    return _klines_to_bars(kl)


def fetch_ohlcv_15m(symbol: str, limit: int = 400) -> List[Bar]:
    _ensure_broker()
    kl = _BROKER.fetch_ohlcv(symbol, interval="15m", limit=limit)
    return _klines_to_bars(kl)


def fetch_btc_context() -> dict:
    """Лёгкий BTC‑контекст: наклон EMA20 и относительная вола → вес 0..1.
    Это простая эвристика, можно заменить на ML/тонкие признаки.
    """
    try:
        bars = fetch_ohlcv_1h("BTCUSDT", limit=60)
    except Exception:
        return {"btc_weight": 0.5}
    if len(bars) < 25:
        return {"btc_weight": 0.5}
    closes = [b.close for b in bars]
    # Простейшая EMA20
    k = 2.0 / (20 + 1)
    ema = closes[0]
    ema_vals = []
    for px in closes:
        ema = (px - ema) * k + ema
        ema_vals.append(ema)
    slope = ema_vals[-1] - ema_vals[-5]
    # Нормированная вола (NATR proxy)
    import statistics
    atr_proxy = statistics.pstdev(closes[-20:]) / max(closes[-1], 1e-9) * 100.0
    w = 0.5
    if slope > 0 and atr_proxy > 0.8:
        w = 0.75
    elif slope < 0 and atr_proxy > 0.8:
        w = 0.25
    return {"btc_weight": max(0.0, min(1.0, w))}
