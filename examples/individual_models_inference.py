# examples/individual_models_inference.py
"""
Пример использования индивидуальных моделей для каждой пары.
Каждая пара имеет свою собственную модель H12 и H24.
"""

from __future__ import annotations
import yaml
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.forecast.lgbm_forecaster import Forecaster
from orchestrator.features.builder import build_features_for_candidate

class IndividualModelInference:
    """Инференс с индивидуальными моделями для каждой пары."""
    
    def __init__(self, config_path: str = "config/models_individual.yaml"):
        """Загружает конфигурацию индивидуальных моделей."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.models: Dict[str, Dict[str, Forecaster]] = {}
        self._load_models()
    
    def _load_models(self):
        """Загружает модели для всех пар."""
        ml_config = self.config.get("ml", {})
        models_config = ml_config.get("models", {})
        
        for symbol, horizons in models_config.items():
            self.models[symbol] = {}
            
            for horizon, model_config in horizons.items():
                model_path = model_config["path"]
                calibrator_path = model_config.get("calibrator")
                
                try:
                    forecaster = Forecaster(
                        model_path=model_path,
                        calibrator_prefer=model_config.get("calibrator_prefer", "isotonic")
                    )
                    self.models[symbol][horizon] = forecaster
                    print(f"✅ Loaded {symbol} {horizon}: {model_path}")
                except Exception as e:
                    print(f"❌ Failed to load {symbol} {horizon}: {e}")
                    self.models[symbol][horizon] = None
    
    def predict_for_symbol(self, symbol: str, features: pd.DataFrame, 
                          horizon: str = "H12") -> float:
        """
        Предсказание для конкретной пары и горизонта.
        
        Args:
            symbol: Торговая пара (например, "ADAUSDT")
            features: DataFrame с фичами
            horizon: "H12" или "H24"
        
        Returns:
            Вероятность успеха (0.0-1.0)
        """
        if symbol not in self.models:
            print(f"⚠️ No models found for {symbol}")
            return 0.5
        
        if horizon not in self.models[symbol]:
            print(f"⚠️ No {horizon} model found for {symbol}")
            return 0.5
        
        forecaster = self.models[symbol][horizon]
        if forecaster is None:
            return 0.5
        
        try:
            prob = forecaster.predict_proba_df(features)
            return float(prob.iloc[0]) if len(prob) > 0 else 0.5
        except Exception as e:
            print(f"❌ Prediction failed for {symbol} {horizon}: {e}")
            return 0.5
    
    def predict_ensemble(self, symbol: str, features: pd.DataFrame) -> Dict[str, float]:
        """
        Предсказание ансамбля H12 + H24 для пары.
        
        Args:
            symbol: Торговая пара
            features: DataFrame с фичами
        
        Returns:
            Словарь с вероятностями для H12, H24 и взвешенным ансамблем
        """
        h12_prob = self.predict_for_symbol(symbol, features, "H12")
        h24_prob = self.predict_for_symbol(symbol, features, "H24")
        
        # Веса ансамбля из конфигурации
        ensemble_config = self.config.get("ml", {}).get("ensemble", {})
        weights = ensemble_config.get("weights", {"H12": 0.5, "H24": 0.5})
        
        w12 = weights.get("H12", 0.5)
        w24 = weights.get("H24", 0.5)
        
        ensemble_prob = w12 * h12_prob + w24 * h24_prob
        
        return {
            "H12": h12_prob,
            "H24": h24_prob,
            "ensemble": ensemble_prob
        }
    
    def get_available_symbols(self) -> list:
        """Возвращает список доступных пар."""
        return list(self.models.keys())
    
    def get_model_info(self, symbol: str) -> Dict[str, Any]:
        """Возвращает информацию о моделях для пары."""
        if symbol not in self.models:
            return {}
        
        info = {}
        for horizon, forecaster in self.models[symbol].items():
            if forecaster is not None:
                meta = forecaster.meta()
                info[horizon] = {
                    "kind": meta.get("kind", "unknown"),
                    "features_count": len(meta.get("feature_names", [])),
                    "task": meta.get("task", "unknown"),
                    "horizon_bars": meta.get("horizon_bars", 0)
                }
            else:
                info[horizon] = {"status": "failed_to_load"}
        
        return info

def demo_individual_inference():
    """Демонстрация использования индивидуальных моделей."""
    print("🚀 Individual Models Inference Demo")
    print("=" * 50)
    
    # Инициализация
    inference = IndividualModelInference()
    
    # Показываем доступные пары
    symbols = inference.get_available_symbols()
    print(f"📊 Available symbols: {', '.join(symbols)}")
    print()
    
    # Создаем тестовые фичи для демонстрации
    test_features = pd.DataFrame({
        'ret_1': [0.01],
        'ret_3': [0.02],
        'ret_6': [0.03],
        'ema20': [100.0],
        'ema50': [99.5],
        'ema200': [98.0],
        'ema20_slope': [0.005],
        'natr14': [2.5],
        'rng_1': [0.02],
        'rng_3': [0.025],
        'z_close_50': [0.5],
        'ret_1_lag1': [0.008],
        'rng_1_lag1': [0.018],
        'ret_1_lag2': [0.012],
        'rng_1_lag2': [0.022],
        'ret_1_lag3': [0.009],
        'rng_1_lag3': [0.019]
    })
    
    # Тестируем несколько пар
    test_symbols = ["ADAUSDT", "DOGEUSDT", "ARBUSDT"]
    
    for symbol in test_symbols:
        print(f"🔍 Testing {symbol}:")
        
        # Информация о моделях
        info = inference.get_model_info(symbol)
        for horizon, model_info in info.items():
            if "status" not in model_info:
                print(f"  {horizon}: {model_info['kind']} ({model_info['features_count']} features)")
            else:
                print(f"  {horizon}: {model_info['status']}")
        
        # Предсказания
        try:
            results = inference.predict_ensemble(symbol, test_features)
            print(f"  H12 prob: {results['H12']:.3f}")
            print(f"  H24 prob: {results['H24']:.3f}")
            print(f"  Ensemble: {results['ensemble']:.3f}")
        except Exception as e:
            print(f"  ❌ Prediction failed: {e}")
        
        print()

if __name__ == "__main__":
    demo_individual_inference()
