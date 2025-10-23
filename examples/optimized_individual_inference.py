# examples/optimized_individual_inference.py
"""
Оптимизированный инференс с индивидуальными моделями.
Включает веса на основе качества, отключение слабых моделей и fail-safes.
"""

from __future__ import annotations
import yaml
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.forecast.lgbm_forecaster import Forecaster
from orchestrator.features.builder import build_features_for_candidate

class OptimizedIndividualInference:
    """Оптимизированный инференс с индивидуальными моделями."""
    
    def __init__(self, config_path: str = "config/models_individual_optimized.yaml"):
        """Загружает оптимизированную конфигурацию."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.models: Dict[str, Dict[str, Forecaster]] = {}
        self.disabled_symbols = set(self.config.get("ml", {}).get("disabled_symbols", []))
        self.min_auc = self.config.get("ml", {}).get("min_auc_threshold", 0.45)
        self._load_models()
    
    def _load_models(self):
        """Загружает модели с учетом оптимизированных весов."""
        ml_config = self.config.get("ml", {})
        models_config = ml_config.get("models", {})
        
        for symbol, horizons in models_config.items():
            if symbol in self.disabled_symbols:
                print(f"🚫 {symbol}: disabled (below min AUC)")
                continue
                
            self.models[symbol] = {}
            
            for horizon, model_config in horizons.items():
                if not model_config.get("enabled", True):
                    print(f"🚫 {symbol} {horizon}: disabled (weak performance)")
                    continue
                
                model_path = model_config["path"]
                calibrator_path = model_config.get("calibrator")
                
                try:
                    forecaster = Forecaster(
                        model_path=model_path,
                        calibrator_prefer=model_config.get("calibrator_prefer", "isotonic")
                    )
                    self.models[symbol][horizon] = forecaster
                    auc = model_config.get("auc", 0.5)
                    weight = model_config.get("weight", 0.5)
                    print(f"✅ {symbol} {horizon}: AUC={auc:.3f}, weight={weight:.1f}")
                except Exception as e:
                    print(f"❌ Failed to load {symbol} {horizon}: {e}")
                    self.models[symbol][horizon] = None
    
    def predict_for_symbol(self, symbol: str, features: pd.DataFrame, 
                          horizon: str = "H12") -> Tuple[float, Dict[str, Any]]:
        """
        Предсказание для конкретной пары и горизонта с метаданными.
        
        Returns:
            (probability, metadata)
        """
        if symbol in self.disabled_symbols:
            return 0.5, {"status": "disabled", "reason": "below_min_auc"}
        
        if symbol not in self.models:
            return 0.5, {"status": "no_models", "reason": "symbol_not_found"}
        
        if horizon not in self.models[symbol]:
            return 0.5, {"status": "no_horizon", "reason": "horizon_disabled"}
        
        forecaster = self.models[symbol][horizon]
        if forecaster is None:
            return 0.5, {"status": "load_failed", "reason": "model_load_error"}
        
        try:
            prob = forecaster.predict_proba_df(features)
            prob_value = float(prob.iloc[0]) if len(prob) > 0 else 0.5
            
            # Получаем метаданные модели
            model_config = self.config["ml"]["models"][symbol][horizon]
            metadata = {
                "status": "success",
                "auc": model_config.get("auc", 0.5),
                "weight": model_config.get("weight", 0.5),
                "enabled": model_config.get("enabled", True)
            }
            
            return prob_value, metadata
            
        except Exception as e:
            return 0.5, {"status": "prediction_failed", "reason": str(e)}
    
    def predict_ensemble(self, symbol: str, features: pd.DataFrame) -> Dict[str, Any]:
        """
        Предсказание ансамбля H12 + H24 с оптимизированными весами.
        """
        if symbol in self.disabled_symbols:
            return {
                "ensemble": 0.5,
                "H12": 0.5,
                "H24": 0.5,
                "weights": {"H12": 0.0, "H24": 0.0},
                "status": "disabled",
                "reason": "symbol_disabled"
            }
        
        # Получаем предсказания для обоих горизонтов
        h12_prob, h12_meta = self.predict_for_symbol(symbol, features, "H12")
        h24_prob, h24_meta = self.predict_for_symbol(symbol, features, "H24")
        
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
        
        return {
            "ensemble": ensemble_prob,
            "H12": h12_prob,
            "H24": h24_prob,
            "weights": {"H12": h12_weight_norm, "H24": h24_weight_norm},
            "metadata": {
                "H12": h12_meta,
                "H24": h24_meta
            },
            "status": "success"
        }
    
    def get_symbol_status(self, symbol: str) -> Dict[str, Any]:
        """Возвращает статус и информацию о моделях для символа."""
        if symbol in self.disabled_symbols:
            return {
                "status": "disabled",
                "reason": "below_min_auc",
                "models": {}
            }
        
        if symbol not in self.models:
            return {
                "status": "not_found",
                "reason": "no_models_available",
                "models": {}
            }
        
        models_info = {}
        for horizon, forecaster in self.models[symbol].items():
            if forecaster is not None:
                meta = forecaster.meta()
                model_config = self.config["ml"]["models"][symbol][horizon]
                models_info[horizon] = {
                    "kind": meta.get("kind", "unknown"),
                    "features_count": len(meta.get("feature_names", [])),
                    "task": meta.get("task", "unknown"),
                    "horizon_bars": meta.get("horizon_bars", 0),
                    "auc": model_config.get("auc", 0.5),
                    "weight": model_config.get("weight", 0.5),
                    "enabled": model_config.get("enabled", True)
                }
            else:
                models_info[horizon] = {"status": "failed_to_load"}
        
        return {
            "status": "active",
            "models": models_info
        }
    
    def get_available_symbols(self) -> list:
        """Возвращает список активных пар."""
        return [s for s in self.models.keys() if s not in self.disabled_symbols]
    
    def get_disabled_symbols(self) -> list:
        """Возвращает список отключенных пар."""
        return list(self.disabled_symbols)

def demo_optimized_inference():
    """Демонстрация оптимизированного инференса."""
    print("🚀 Optimized Individual Models Inference Demo")
    print("=" * 60)
    
    # Инициализация
    inference = OptimizedIndividualInference()
    
    # Показываем статус всех пар
    all_symbols = ["ADAUSDT", "HBARUSDT", "LTCUSDT", "PNUTUSDT", "WIFUSDT", 
                   "ENAUSDT", "DOGEUSDT", "ARBUSDT", "SUIUSDT", "SEIUSDT"]
    
    print("📊 Symbol Status:")
    for symbol in all_symbols:
        status = inference.get_symbol_status(symbol)
        print(f"  {symbol}: {status['status']}")
        if status['status'] == 'active':
            for horizon, model_info in status['models'].items():
                if 'auc' in model_info:
                    print(f"    {horizon}: AUC={model_info['auc']:.3f}, weight={model_info['weight']:.1f}")
    
    print(f"\n✅ Active symbols: {len(inference.get_available_symbols())}")
    print(f"🚫 Disabled symbols: {len(inference.get_disabled_symbols())}")
    
    # Создаем тестовые фичи
    test_features = pd.DataFrame({
        'ret_1': [0.01], 'ret_3': [0.02], 'ret_6': [0.03],
        'ema20': [100.0], 'ema50': [99.5], 'ema200': [98.0],
        'ema20_slope': [0.005], 'natr14': [2.5], 'rng_1': [0.02],
        'rng_3': [0.025], 'z_close_50': [0.5], 'ret_1_lag1': [0.008],
        'rng_1_lag1': [0.018], 'ret_1_lag2': [0.012], 'rng_1_lag2': [0.022],
        'ret_1_lag3': [0.009], 'rng_1_lag3': [0.019]
    })
    
    # Тестируем активные пары
    active_symbols = inference.get_available_symbols()[:3]  # Первые 3
    
    print(f"\n🔍 Testing active symbols:")
    for symbol in active_symbols:
        print(f"\n  {symbol}:")
        results = inference.predict_ensemble(symbol, test_features)
        
        if results["status"] == "success":
            print(f"    H12: {results['H12']:.3f} (weight: {results['weights']['H12']:.1f})")
            print(f"    H24: {results['H24']:.3f} (weight: {results['weights']['H24']:.1f})")
            print(f"    Ensemble: {results['ensemble']:.3f}")
        else:
            print(f"    Status: {results['status']}")

if __name__ == "__main__":
    demo_optimized_inference()
