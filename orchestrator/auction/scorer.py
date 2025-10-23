from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import os
import yaml
import numpy as np
import pandas as pd
from dataclasses import dataclass

from ..utils.types import SignalCandidate, FirstHitForecast, ScoredCandidate

# === NEW: опциональный ML ===
try:
    from ..forecast.lgbm_forecaster import Forecaster
    from ..features.builder import build_features_for_candidate
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False

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
    config_path: Optional[str] = None  # путь к models_individual_optimized.yaml
    calibrator_prefer: Optional[str] = "isotonic"  # "isotonic"|"platt"|None
    # как именно влиять на EV через prob:
    prob_weight_base: float = 1.0   # базовый множитель EV
    prob_weight_gain: float = 1.0   # усиление в зависимости от (p-0.5), симметрично
    min_auc_threshold: float = 0.45  # минимальный AUC для использования модели


class IndividualMLManager:
    """Менеджер для индивидуальных ML моделей."""
    
    def __init__(self, config_path: str = "config/models_individual_optimized.yaml"):
        self.config_path = config_path
        self.config = None
        self.models: Dict[str, Dict[str, Forecaster]] = {}
        self.disabled_symbols = set()
        self._load_config()
        self._load_models()
    
    def _load_config(self):
        """Загружает конфигурацию моделей."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            self.disabled_symbols = set(self.config.get("ml", {}).get("disabled_symbols", []))
        except Exception as e:
            print(f"❌ Failed to load ML config: {e}")
            self.config = {"ml": {"enabled": False}}
    
    def _load_models(self):
        """Загружает модели для всех активных пар."""
        if not self.config or not self.config.get("ml", {}).get("enabled", False):
            return
        
        models_config = self.config.get("ml", {}).get("models", {})
        
        for symbol, horizons in models_config.items():
            if symbol in self.disabled_symbols:
                continue
                
            self.models[symbol] = {}
            
            for horizon, model_config in horizons.items():
                if not model_config.get("enabled", True):
                    continue
                
                try:
                    model_path = model_config["path"]
                    forecaster = Forecaster(
                        model_path=model_path,
                        calibrator_prefer=model_config.get("calibrator_prefer", "isotonic")
                    )
                    self.models[symbol][horizon] = forecaster
                except Exception as e:
                    print(f"❌ Failed to load {symbol} {horizon}: {e}")
                    self.models[symbol][horizon] = None
    
    def predict_ensemble(self, symbol: str, features: pd.DataFrame) -> Tuple[float, Dict[str, Any]]:
        """
        Предсказание ансамбля H12 + H24 для символа.
        
        Returns:
            (ensemble_probability, metadata)
        """
        if symbol in self.disabled_symbols:
            return 0.5, {"status": "disabled", "reason": "below_min_auc"}
        
        if symbol not in self.models:
            return 0.5, {"status": "no_models", "reason": "symbol_not_found"}
        
        # Получаем предсказания для обоих горизонтов
        h12_prob, h12_meta = self._predict_horizon(symbol, features, "H12")
        h24_prob, h24_meta = self._predict_horizon(symbol, features, "H24")
        
        # Получаем веса из конфигурации
        model_config = self.config["ml"]["models"].get(symbol, {})
        h12_weight = model_config.get("H12", {}).get("weight", 0.5)
        h24_weight = model_config.get("H24", {}).get("weight", 0.5)
        
        # Нормализуем веса
        total_weight = h12_weight + h24_weight
        if total_weight > 0:
            h12_weight_norm = h12_weight / total_weight
            h24_weight_norm = h24_weight / total_weight
        else:
            h12_weight_norm = 0.5
            h24_weight_norm = 0.5
        
        # Вычисляем ансамбль
        ensemble_prob = h12_weight_norm * h12_prob + h24_weight_norm * h24_prob
        
        metadata = {
            "ensemble": ensemble_prob,
            "H12": h12_prob,
            "H24": h24_prob,
            "weights": {"H12": h12_weight_norm, "H24": h24_weight_norm},
            "status": "success"
        }
        
        return ensemble_prob, metadata
    
    def _predict_horizon(self, symbol: str, features: pd.DataFrame, horizon: str) -> Tuple[float, Dict[str, Any]]:
        """Предсказание для конкретного горизонта."""
        if horizon not in self.models[symbol]:
            return 0.5, {"status": "no_horizon", "reason": "horizon_disabled"}
        
        forecaster = self.models[symbol][horizon]
        if forecaster is None:
            return 0.5, {"status": "load_failed", "reason": "model_load_error"}
        
        try:
            prob = forecaster.predict_proba_df(features)
            prob_value = float(prob.iloc[0]) if len(prob) > 0 else 0.5
            return prob_value, {"status": "success"}
        except Exception as e:
            return 0.5, {"status": "prediction_failed", "reason": str(e)}
    
    def is_symbol_enabled(self, symbol: str) -> bool:
        """Проверяет, включена ли пара для ML."""
        return symbol not in self.disabled_symbols and symbol in self.models
    
    def get_available_symbols(self) -> list:
        """Возвращает список активных пар."""
        return [s for s in self.models.keys() if s not in self.disabled_symbols]
    
    def get_disabled_symbols(self) -> list:
        """Возвращает список отключенных пар."""
        return list(self.disabled_symbols)


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


def score_candidates(cands: List[SignalCandidate], forecasts: List[FirstHitForecast], btc_weight: float, ml_cfg: Optional[MLConfig] = None, ohlc_1h_by_symbol: Optional[Dict[str, pd.DataFrame]] = None, _ml_manager: Optional[IndividualMLManager] = None) -> List[ScoredCandidate]:
    # === NEW: инициализация ML ===
    _forecaster: Optional[Forecaster] = None
    if ML_AVAILABLE and ml_cfg and ml_cfg.enabled:
        # Приоритет: IndividualMLManager > старый Forecaster
        if _ml_manager is None:
            path = ml_cfg.config_path or ml_cfg.model_path or os.environ.get("FORECASTER_MODEL_PATH", None)
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
            if ohlc_1h_by_symbol:
                ohlc_1h = ohlc_1h_by_symbol.get(c.symbol)
                if isinstance(ohlc_1h, pd.DataFrame) and not ohlc_1h.empty:
                    try:
                        # Приоритет: IndividualMLManager > старый Forecaster
                        if _ml_manager and _ml_manager.is_symbol_enabled(c.symbol):
                            # Используем индивидуальные модели
                            feats_row = build_features_for_candidate(ohlc_1h, c.symbol, include_symbol_onehot=False)
                            prob, metadata = _ml_manager.predict_ensemble(c.symbol, feats_row)
                            
                            # Получаем веса из конфигурации модели
                            model_config = _ml_manager.config["ml"]["models"].get(c.symbol, {})
                            base = model_config.get("H12", {}).get("prob_weight_base", ml_cfg.prob_weight_base if ml_cfg else 1.0)
                            gain = model_config.get("H12", {}).get("prob_weight_gain", ml_cfg.prob_weight_gain if ml_cfg else 1.0)
                            
                        elif _forecaster:
                            # Fallback к старому Forecaster
                            feats_row = build_features_for_candidate(ohlc_1h, c.symbol, include_symbol_onehot=True)
                            prob = float(_forecaster.predict_proba_df(feats_row).iloc[0])
                            base = ml_cfg.prob_weight_base if ml_cfg else 1.0
                            gain = ml_cfg.prob_weight_gain if ml_cfg else 1.0
                        else:
                            continue  # Нет ML, пропускаем

                        # Мягкая линейная модуляция EV вокруг 0.5
                        weight = base + gain * (prob - 0.5) * 2.0 * 0.5
                        # пояснение: (prob-0.5) в [-0.5; +0.5], умножение даёт диапазон ~base±(gain*0.5)
                        e_adj = e_adj * max(0.0, weight)
                        
                        # safety: если вдруг NaN
                        if not np.isfinite(e_adj):
                            e_adj = e / (1.0 + TIME_ALPHA * t_first)  # fallback к исходному
                    except Exception:
                        pass  # fallback к исходному EV
            
            # мягкая поправка BTC_weight (ослабляем тренд-влияние)
            if c.type == "TRND" and btc_weight > 0.7:
                e_adj *= 1.01  # уменьшили бонус с 1.02 до 1.01
            if c.type == "BRK" and btc_weight < 0.3:
                e_adj *= 0.99  # уменьшили штраф с 0.98 до 0.99
            
            # Штраф за MTF-конфликт (мягкий, не блокирующий)
            if hasattr(ctx, 'mtf') and ctx.mtf.bias_against(c.symbol, c.side):
                e_adj *= 0.85  # штраф 15%, но не блок
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
