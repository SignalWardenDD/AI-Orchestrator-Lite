# enhanced_lgbm_forecaster_example.py
"""
Пример расширенного LGBMForecaster с интеграцией обученных моделей и калибраторов.
Показывает, как безопасно интегрировать новые модули в существующий код.
"""

from __future__ import annotations
import os, json, glob
from typing import Iterable, List, Dict, Any, Optional
import numpy as np
import pandas as pd

# Импорты существующих модулей
from orchestrator.forecast.base import Forecaster
from orchestrator.utils.types import SignalCandidate, FirstHitForecast

# Импорты новых модулей
from orchestrator.forecast.calibrators import Calibrator
from orchestrator.utils.mathx import natr, atr, ewma, zscore, pct_change_safe

# Optional ML deps
try:
    import lightgbm as lgb
    import joblib
    LGB_OK = True
except Exception:
    LGB_OK = False

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    SK_OK = True
except Exception:
    SK_OK = False


class EnhancedLGBMForecaster(Forecaster):
    """
    Расширенный LGBMForecaster с поддержкой:
    - Автоматической загрузки обученных моделей
    - Калиброванных вероятностей
    - Fallback режимов без ML
    """
    
    def __init__(self, type_name: str, models_dir: str = "forecast/models"):
        self.type_name = type_name
        self.models_dir = models_dir
        self.models = {}  # {horizon: model}
        self.calibrators = {}  # {horizon: calibrator}
        self.feature_names = []
        self.meta = {}
        
        # Автоматическая загрузка моделей
        self._load_models()
    
    def _load_models(self):
        """Автоматическая загрузка обученных моделей из директории."""
        if not os.path.exists(self.models_dir):
            print(f"⚠️  Директория моделей не найдена: {self.models_dir}")
            return
        
        # Поиск моделей для данного типа
        pattern = os.path.join(self.models_dir, f"*{self.type_name}*.joblib")
        model_files = glob.glob(pattern)
        
        if not model_files:
            print(f"⚠️  Модели для типа {self.type_name} не найдены")
            return
        
        for model_path in model_files:
            try:
                # Загрузка модели
                if LGB_OK and SK_OK:
                    model_data = joblib.load(model_path)
                    model = model_data["model"]
                    meta = model_data.get("meta", {})
                else:
                    # Fallback для случая без ML библиотек
                    model = None
                    meta = {}
                
                # Определение горизонта из имени файла или метаданных
                horizon = self._extract_horizon(model_path, meta)
                
                if horizon:
                    self.models[horizon] = model
                    self.meta[horizon] = meta
                    self.feature_names = meta.get("feature_names", [])
                    
                    # Попытка загрузки калибратора
                    self._load_calibrator(horizon, model_path)
                    
                    print(f"✅ Загружена модель для горизонта {horizon}: {os.path.basename(model_path)}")
                
            except Exception as e:
                print(f"❌ Ошибка загрузки модели {model_path}: {e}")
    
    def _extract_horizon(self, model_path: str, meta: Dict) -> Optional[int]:
        """Извлечение горизонта из пути к модели или метаданных."""
        # Из метаданных
        if "horizon_bars" in meta:
            return meta["horizon_bars"]
        
        # Из имени файла (например, "binary_hit_ADAUSDT_H24.joblib")
        import re
        match = re.search(r'H(\d+)', os.path.basename(model_path))
        if match:
            return int(match.group(1))
        
        return None
    
    def _load_calibrator(self, horizon: int, model_path: str):
        """Загрузка калибратора для модели."""
        # Поиск калибратора
        base_name = os.path.splitext(model_path)[0]
        calib_patterns = [
            f"{base_name}.calib.platt.joblib",
            f"{base_name}.calib.isotonic.joblib"
        ]
        
        for calib_path in calib_patterns:
            if os.path.exists(calib_path):
                try:
                    calibrator = Calibrator.load(calib_path)
                    self.calibrators[horizon] = calibrator
                    print(f"✅ Загружен калибратор для горизонта {horizon}: {os.path.basename(calib_path)}")
                    break
                except Exception as e:
                    print(f"⚠️  Ошибка загрузки калибратора {calib_path}: {e}")
    
    def _extract_features(self, candidate: SignalCandidate, ohlc_data: Optional[pd.DataFrame] = None) -> pd.Series:
        """
        Извлечение признаков для кандидата.
        Использует те же признаки, что и при обучении.
        """
        if ohlc_data is None:
            # Fallback: базовые признаки из кандидата
            features = pd.Series({
                'ret_1': 0.0,
                'ret_3': 0.0,
                'ret_6': 0.0,
                'ema20': candidate.ema20,
                'ema50': candidate.ema20,  # fallback
                'ema200': candidate.ema20,  # fallback
                'ema20_slope': 0.0,
                'natr14': candidate.atr / candidate.entry_price * 100,
                'rng_1': 0.0,
                'rng_3': 0.0,
                'z_close_50': 0.0,
                'ret_1_lag1': 0.0,
                'ret_1_lag2': 0.0,
                'ret_1_lag3': 0.0,
                'rng_1_lag1': 0.0,
                'rng_1_lag2': 0.0,
                'rng_1_lag3': 0.0,
                f'sym__{candidate.symbol}': 1.0
            })
        else:
            # Полные признаки из OHLC данных
            close = ohlc_data['close']
            high, low = ohlc_data['high'], ohlc_data['low']
            
            features = pd.Series({
                'ret_1': pct_change_safe(close, 1).iloc[-1],
                'ret_3': pct_change_safe(close, 3).iloc[-1],
                'ret_6': pct_change_safe(close, 6).iloc[-1],
                'ema20': ewma(close, 20).iloc[-1],
                'ema50': ewma(close, 50).iloc[-1],
                'ema200': ewma(close, 200).iloc[-1],
                'ema20_slope': pct_change_safe(ewma(close, 20), 1).iloc[-1],
                'natr14': natr(high, low, close, 14).iloc[-1],
                'rng_1': ((high - low) / close.replace(0.0, np.nan)).iloc[-1],
                'rng_3': ((high - low) / close.replace(0.0, np.nan)).rolling(3).mean().iloc[-1],
                'z_close_50': zscore(close - ewma(close, 50), window=50).iloc[-1],
                'ret_1_lag1': pct_change_safe(close, 1).shift(1).iloc[-1],
                'ret_1_lag2': pct_change_safe(close, 1).shift(2).iloc[-1],
                'ret_1_lag3': pct_change_safe(close, 1).shift(3).iloc[-1],
                'rng_1_lag1': ((high - low) / close.replace(0.0, np.nan)).shift(1).iloc[-1],
                'rng_1_lag2': ((high - low) / close.replace(0.0, np.nan)).shift(2).iloc[-1],
                'rng_1_lag3': ((high - low) / close.replace(0.0, np.nan)).shift(3).iloc[-1],
                f'sym__{candidate.symbol}': 1.0
            })
        
        # Заполнение NaN значений
        features = features.fillna(0.0)
        
        # Приведение к нужному порядку признаков
        if self.feature_names:
            # Создаем Series с правильным порядком
            ordered_features = pd.Series(index=self.feature_names, dtype=float)
            for name in self.feature_names:
                if name in features:
                    ordered_features[name] = features[name]
                else:
                    ordered_features[name] = 0.0
            return ordered_features
        
        return features
    
    def _predict_raw(self, model: Any, features: pd.Series, horizon: int) -> float:
        """Получение сырого предсказания от модели."""
        if model is None:
            # Fallback: простая эвристика
            return 0.5
        
        try:
            if hasattr(model, 'predict'):
                # LightGBM или sklearn модель
                if len(features.shape) == 1:
                    features = features.values.reshape(1, -1)
                return float(model.predict(features)[0])
            elif isinstance(model, dict) and "weights" in model:
                # Linear fallback модель
                weights = np.array(model["weights"])
                values = features.values[:len(weights)]
                raw_score = np.dot(values, weights)
                # Нормализация в [0, 1]
                return float(np.clip(raw_score, 0.0, 1.0))
            else:
                return 0.5
        except Exception as e:
            print(f"⚠️  Ошибка предсказания для горизонта {horizon}: {e}")
            return 0.5
    
    def _calibrate_probability(self, raw_score: float, horizon: int) -> float:
        """Калибровка сырого предсказания в вероятность."""
        if horizon in self.calibrators:
            try:
                calibrator = self.calibrators[horizon]
                calibrated = calibrator.predict_proba(np.array([raw_score]))[0]
                return float(calibrated)
            except Exception as e:
                print(f"⚠️  Ошибка калибровки для горизонта {horizon}: {e}")
        
        # Fallback: простая нормализация
        return float(np.clip(raw_score, 0.0, 1.0))
    
    def predict_many(self, candidates: Iterable[SignalCandidate], horizons: List[int]) -> List[FirstHitForecast]:
        """Предсказание для множества кандидатов."""
        out: List[FirstHitForecast] = []
        
        for candidate in candidates:
            if candidate.type != self.type_name:
                continue
            
            # Извлечение признаков
            features = self._extract_features(candidate)
            
            for horizon in horizons:
                if horizon not in self.models:
                    # Fallback: базовые вероятности
                    out.append(FirstHitForecast(
                        symbol=candidate.symbol,
                        type=candidate.type,
                        side=candidate.side,
                        H=horizon,
                        p_hit={"tp1": 0.2, "tp2": 0.15, "tp3": 0.1, "tp4": 0.05, "sl": 0.5},
                        t_hit={"tp1": 2.0, "tp2": 3.0, "tp3": 5.0, "tp4": 7.0, "sl": 2.5},
                        fill_prob=0.7,
                        slip_est=0.0008,
                        conf_type=0.5,
                        flags={"exhaustion": False, "inversion": False}
                    ))
                    continue
                
                # Получение сырого предсказания
                model = self.models[horizon]
                raw_score = self._predict_raw(model, features, horizon)
                
                # Калибровка вероятности
                calibrated_prob = self._calibrate_probability(raw_score, horizon)
                
                # Создание прогноза
                forecast = self._create_forecast(candidate, horizon, calibrated_prob)
                out.append(forecast)
        
        return out
    
    def _create_forecast(self, candidate: SignalCandidate, horizon: int, prob: float) -> FirstHitForecast:
        """Создание прогноза на основе вероятности."""
        # Базовые вероятности (можно настроить)
        base_probs = {
            "tp1": 0.2, "tp2": 0.15, "tp3": 0.1, "tp4": 0.05, "sl": 0.5
        }
        
        # Масштабирование на основе предсказанной вероятности
        scale_factor = prob * 2.0  # 0.5 -> 1.0, 1.0 -> 2.0
        
        p_hit = {}
        for key, base_prob in base_probs.items():
            if key == "sl":
                # SL вероятность обратно пропорциональна успеху
                p_hit[key] = max(0.1, min(0.8, base_prob * (2.0 - scale_factor)))
            else:
                # TP вероятности пропорциональны успеху
                p_hit[key] = max(0.01, min(0.5, base_prob * scale_factor))
        
        # Нормализация вероятностей
        total_prob = sum(p_hit.values())
        if total_prob > 1.0:
            for key in p_hit:
                p_hit[key] /= total_prob
        
        return FirstHitForecast(
            symbol=candidate.symbol,
            type=candidate.type,
            side=candidate.side,
            H=horizon,
            p_hit=p_hit,
            t_hit={"tp1": 2.0, "tp2": 3.0, "tp3": 5.0, "tp4": 7.0, "sl": 2.5},
            fill_prob=0.7,
            slip_est=0.0008,
            conf_type=prob,
            flags={"exhaustion": False, "inversion": False}
        )


# Пример использования
def create_enhanced_forecast_registry(models_dir: str = "forecast/models") -> Dict[str, EnhancedLGBMForecaster]:
    """
    Создание расширенного реестра прогнозистов с автоматической загрузкой моделей.
    """
    registry = {}
    
    # Типы моделей
    model_types = ["BRK", "PB", "TRND", "BB"]
    
    for model_type in model_types:
        try:
            forecaster = EnhancedLGBMForecaster(model_type, models_dir)
            registry[model_type] = forecaster
            print(f"✅ Создан прогнозист для типа {model_type}")
        except Exception as e:
            print(f"❌ Ошибка создания прогнозиста для типа {model_type}: {e}")
    
    return registry


if __name__ == "__main__":
    # Пример использования
    print("🔧 Создание расширенного реестра прогнозистов...")
    
    registry = create_enhanced_forecast_registry()
    
    print(f"📊 Создано прогнозистов: {len(registry)}")
    
    for model_type, forecaster in registry.items():
        print(f"  {model_type}: {len(forecaster.models)} моделей, {len(forecaster.calibrators)} калибраторов")
