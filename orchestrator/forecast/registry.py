# orchestrator/forecast/registry.py
"""
Реестр моделей с поддержкой per-signal моделей и fallback.
"""

from pathlib import Path
import joblib
import json
import numpy as np
from typing import Optional, Tuple, Dict, Any

class PerSignalRegistry:
    def __init__(self, cfg):
        # cfg.ml.models_per_signal.yaml_path — путь к YAML карте (см. ниже)
        # cfg.ml.models_individual.yaml_path — общий фолбэк
        self.cfg = cfg
        self._cache: Dict[Tuple[str, Optional[str], str], dict] = {}
        
        # Поддержка как объекта, так и словаря
        if hasattr(cfg, 'ml') and isinstance(cfg.ml, dict):
            per_signal_path = cfg.ml.get('models_per_signal', {}).get('yaml_path', 'config/optimized/models_per_signal_optimized.yaml')
            individual_path = cfg.ml.get('models_individual', {}).get('yaml_path', 'config/optimized/models_individual_optimized.yaml')
        elif hasattr(cfg, 'ml'):
            # cfg.ml может быть простым объектом/неймспейсом
            per_signal_path = getattr(getattr(cfg.ml, 'models_per_signal', None), 'yaml_path', 'config/optimized/models_per_signal_optimized.yaml')
            individual_path = getattr(getattr(cfg.ml, 'models_individual', None), 'yaml_path', 'config/optimized/models_individual_optimized.yaml')
        else:
            # безопасный дефолт
            per_signal_path = 'config/optimized/models_per_signal_optimized.yaml'
            individual_path = 'config/optimized/models_individual_optimized.yaml'
        
        self._map = self._load_yaml(per_signal_path)
        self._fallback = self._load_yaml(individual_path)

    def _load_yaml(self, path):
        import yaml
        with open(path) as f: 
            return yaml.safe_load(f)

    def get(self, symbol: str, signal: Optional[str], horizon: str):
        """Вернёт бандл {'model','calibrator','feature_names'} или None."""
        key = (symbol, signal, horizon)
        if key in self._cache: 
            return self._cache[key]
    
    def get_model(self, symbol: str, signal: Optional[str], horizon: str):
        """Алиас для get."""
        return self.get(symbol, signal, horizon)
        entry = None
        if signal and symbol in self._map and signal in self._map[symbol] and horizon in self._map[symbol][signal]:
            entry = self._map[symbol][signal][horizon]
        if not entry:
            # FALLBACK: без сигнала (общая модель на пару/горизонт)
            if symbol in self._fallback and horizon in self._fallback[symbol]:
                entry = self._fallback[symbol][horizon]

        if not entry: 
            return None

        model_obj = joblib.load(entry["model_path"])
        calib = joblib.load(entry["calibrator_path"]) if entry.get("calibrator_path") else None

        if isinstance(model_obj, dict) and "model" in model_obj:
            model = model_obj["model"]
            fcols = model_obj.get("feature_names", entry.get("feature_names"))
        else:
            model = model_obj
            fcols = entry.get("feature_names")

        bundle = {
            "model": model,
            "calibrator": calib,
            "feature_names": fcols,
            "weights": entry.get("weights", 1.0),
            "ev_min": float(entry.get("ev_min", 0.10)),
        }
        self._cache[key] = bundle
        return bundle

# Для обратной совместимости
ForecastRegistry = PerSignalRegistry