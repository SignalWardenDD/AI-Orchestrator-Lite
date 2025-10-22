from __future__ import annotations
from typing import Dict, List, Optional
import os
import numpy as np
import pandas as pd
from dataclasses import dataclass

from ..utils.types import SignalCandidate, FirstHitForecast, ScoredCandidate

# === NEW: опциональный ML ===
try:
    from forecast.lgbm_forecaster import Forecaster
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False

from features.builder import build_features_for_candidate  # NEW

# Денежный скор по лесенке TP и SL + временной вес + BTC_weight.

TP_LADDER = [
    (0.20, 0.6),  # 20% @ +0.6×ATR
    (0.25, 1.2),
    (0.25, 2.0),
    (0.30, 3.2),
]
SL_MULT = {"BRK": 1.3, "PB": 2.0, "TRND": 1.8, "BB": 1.6}
BE_STEPS = {"after_tp1": 0.15, "after_tp2": 0.35, "after_tp3": 0.80}

TIME_ALPHA = 0.05


@dataclass
class MLConfig:
    enabled: bool = True
    model_path: Optional[str] = None  # путь к *.joblib, если None — попытаемся взять из ENV
    calibrator_prefer: Optional[str] = None  # "isotonic"|"platt"|None
    # как именно влиять на EV через prob:
    prob_weight_base: float = 1.0   # базовый множитель EV
    prob_weight_gain: float = 1.0   # усиление в зависимости от (p-0.5), симметрично


def _expected_pnl_usdt(c: SignalCandidate, f: FirstHitForecast, fee_perc: float = 0.0008) -> float:
    atr = c.atr
    # Профит по ступеням в USDT, на фикс номинал не завязываемся здесь (скор — на 1 единицу цены)
    pnl_tp = 0.0
    for pct, mult in TP_LADDER:
        pnl_tp += pct * (mult * atr)
    pnl_sl = - SL_MULT.get(c.type, 1.6) * atr
    # Ожидание: Σ p_hit[k]*PnL_k (упрощённо)
    e = (
        f.p_hit.get("tp1",0)*TP_LADDER[0][1]*atr*TP_LADDER[0][0] +
        f.p_hit.get("tp2",0)*TP_LADDER[1][1]*atr*TP_LADDER[1][0] +
        f.p_hit.get("tp3",0)*TP_LADDER[2][1]*atr*TP_LADDER[2][0] +
        f.p_hit.get("tp4",0)*TP_LADDER[3][1]*atr*TP_LADDER[3][0] +
        f.p_hit.get("sl",0) * pnl_sl
    )
    # Комиссии + ожидаемое проскальзывание
    e -= fee_perc * abs(1)  # нормализация; в реале умножишь на qty*price
    e -= f.slip_est
    return e


def score_candidates(cands: List[SignalCandidate], forecasts: List[FirstHitForecast], btc_weight: float, ml_cfg: Optional[MLConfig] = None, ohlc_1h_by_symbol: Optional[Dict[str, pd.DataFrame]] = None) -> List[ScoredCandidate]:
    # === NEW: инициализация ML ===
    _forecaster: Optional[Forecaster] = None
    if ML_AVAILABLE and ml_cfg and ml_cfg.enabled:
        path = ml_cfg.model_path or os.environ.get("FORECASTER_MODEL_PATH", None)
        if path and os.path.exists(path):
            try:
                _forecaster = Forecaster(path, calibrator_prefer=ml_cfg.calibrator_prefer)
            except Exception:
                _forecaster = None

    # Индексируем прогнозы по (symbol,type,side,H)
    by_key: Dict[tuple, FirstHitForecast] = {}
    for fr in forecasts:
        by_key[(fr.symbol, fr.type, fr.side, fr.H)] = fr

    out: List[ScoredCandidate] = []
    for c in cands:
        best_score = None
        best_H = None
        for H in (2,4,6,10):
            fr = by_key.get((c.symbol, c.type, c.side, H))
            if not fr:
                continue
            e = _expected_pnl_usdt(c, fr)
            # временной вес
            t_first = min(fr.t_hit.values()) if fr.t_hit else 1.0
            e_adj = e / (1.0 + TIME_ALPHA * t_first)
            
            # === NEW: ML-модуляция EV ===
            if _forecaster and ohlc_1h_by_symbol:
                ohlc_1h = ohlc_1h_by_symbol.get(c.symbol)
                if isinstance(ohlc_1h, pd.DataFrame) and not ohlc_1h.empty:
                    try:
                        # соберём совместимые фичи (как в тренере)
                        feats_row = build_features_for_candidate(ohlc_1h, c.symbol, include_symbol_onehot=True)
                        prob = float(_forecaster.predict_proba_df(feats_row).iloc[0])

                        # мягкая линейная модуляция EV вокруг 0.5
                        base = ml_cfg.prob_weight_base if ml_cfg else 1.0
                        gain = ml_cfg.prob_weight_gain if ml_cfg else 1.0
                        weight = base + gain * (prob - 0.5) * 2.0 * 0.5
                        # пояснение: (prob-0.5) в [-0.5; +0.5], умножение даёт диапазон ~base±(gain*0.5)
                        e_adj = e_adj * max(0.0, weight)
                        
                        # safety: если вдруг NaN
                        if not np.isfinite(e_adj):
                            e_adj = e / (1.0 + TIME_ALPHA * t_first)  # fallback к исходному
                    except Exception:
                        pass  # fallback к исходному EV
            
            # мягкая поправка BTC_weight
            if c.type == "TRND" and btc_weight > 0.7:
                e_adj *= 1.02
            if c.type == "BRK" and btc_weight < 0.3:
                e_adj *= 0.98
            if best_score is None or e_adj > best_score:
                best_score = e_adj
                best_H = H
        if best_score is None:
            continue
        out.append(ScoredCandidate(
            symbol=c.symbol,
            type=c.type,
            side=c.side,
            H_best=best_H or 4,
            score_usdt=float(best_score),
            components={"btc_weight": btc_weight, "time_alpha": TIME_ALPHA}
        ))
    return out
