# enhanced_pipeline_integration.py
"""
Пример интеграции ML функциональности в существующий пайплайн.
Показывает, как безопасно добавить ML скоринг без изменения существующего кода.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd

# Импорты существующих модулей
from orchestrator.utils.types import SignalCandidate, FirstHitForecast
from orchestrator.auction.scorer import score_candidates, MLConfig
from orchestrator.engine.feature_cache import get_feature_cache

# Импорты новых модулей
from orchestrator.data.ingest import fetch_ohlcv_1h
from orchestrator.data.features import build_feature_rows


class EnhancedAnalyzePipeline:
    """
    Пример расширенного пайплайна с ML интеграцией.
    Показывает, как интегрировать ML функциональность в существующий код.
    """
    
    def __init__(self, symbols: List[str], settings: Dict):
        self.symbols = symbols
        self.settings = settings
        
        # Инициализация ML конфигурации
        self.ml_config = self._init_ml_config()
        
        # Инициализация кэша признаков
        self.feature_cache = get_feature_cache(
            ttl_seconds=settings.get("ml", {}).get("performance", {}).get("cache_ttl_seconds", 300)
        )
        
        # Флаг использования ML
        self.use_ml = settings.get("ml", {}).get("enabled", True)
        
        print(f"🔧 ML интеграция: {'включена' if self.use_ml else 'отключена'}")
        if self.ml_config:
            print(f"  Модель: {self.ml_config.model_path}")
            print(f"  Калибратор: {self.ml_config.calibrator_prefer}")
    
    def _init_ml_config(self) -> Optional[MLConfig]:
        """Инициализация ML конфигурации из настроек."""
        ml_settings = self.settings.get("ml", {})
        
        if not ml_settings.get("enabled", True):
            return None
        
        return MLConfig(
            enabled=ml_settings.get("enabled", True),
            model_path=ml_settings.get("model_path"),
            calibrator_prefer=ml_settings.get("calibrator_prefer"),
            prob_weight_base=ml_settings.get("prob_weight_base", 1.0),
            prob_weight_gain=ml_settings.get("prob_weight_gain", 1.0)
        )
    
    def _collect_ohlc_data(self) -> Dict[str, pd.DataFrame]:
        """Сбор OHLC данных для всех символов."""
        ohlc_data = {}
        
        for symbol in self.symbols:
            try:
                # Загрузка OHLC данных
                bars = fetch_ohlcv_1h(symbol, limit=220)
                frows = build_feature_rows(bars)
                
                # Конвертация в DataFrame
                df = pd.DataFrame(frows)
                ohlc_data[symbol] = df
                
                print(f"✅ OHLC данные для {symbol}: {len(df)} баров")
                
            except Exception as e:
                print(f"⚠️  Ошибка загрузки OHLC для {symbol}: {e}")
                ohlc_data[symbol] = pd.DataFrame()
        
        return ohlc_data
    
    def _get_enhanced_ohlc_data(self) -> Dict[str, pd.DataFrame]:
        """Получение OHLC данных с кэшированием признаков."""
        ohlc_data = self._collect_ohlc_data()
        
        # Предварительное кэширование признаков
        if self.use_ml:
            for symbol, df in ohlc_data.items():
                if not df.empty:
                    try:
                        # Кэшируем признаки для символа
                        self.feature_cache.get_features(symbol, df)
                        print(f"📊 Признаки для {symbol} закэшированы")
                    except Exception as e:
                        print(f"⚠️  Ошибка кэширования признаков для {symbol}: {e}")
        
        return ohlc_data
    
    def run_once(self):
        """Основной цикл с ML интеграцией."""
        print("🚀 Запуск цикла анализа с ML интеграцией...")
        
        # Сбор кандидатов (существующая логика)
        all_cands = self._collect_candidates()
        if not all_cands:
            print("ℹ️  Кандидаты не найдены")
            return
        
        print(f"📊 Найдено кандидатов: {len(all_cands)}")
        
        # Прогнозирование (существующая логика)
        forecasts = self._get_forecasts(all_cands)
        print(f"🔮 Создано прогнозов: {len(forecasts)}")
        
        # BTC контекст (существующая логика)
        btc_weight = self._get_btc_weight()
        print(f"₿ BTC вес: {btc_weight:.3f}")
        
        # Сбор OHLC данных для ML
        ohlc_data = self._get_enhanced_ohlc_data()
        
        # ML-улучшенный скоринг
        if self.use_ml and self.ml_config:
            print("🤖 Использование ML скоринга...")
            scored = score_candidates(
                all_cands, forecasts, btc_weight, 
                ml_cfg=self.ml_config, 
                ohlc_1h_by_symbol=ohlc_data
            )
        else:
            print("📊 Использование стандартного скоринга...")
            scored = score_candidates(all_cands, forecasts, btc_weight)
        
        print(f"🎯 Скорировано кандидатов: {len(scored)}")
        
        # Выбор победителя (существующая логика)
        if scored:
            winner = max(scored, key=lambda x: x.score_usdt)
            print(f"🏆 Победитель: {winner.symbol} {winner.type} {winner.side} (скор: {winner.score_usdt:.4f})")
            
            # ML информация
            if self.use_ml and hasattr(winner, 'components'):
                components = winner.components
                if 'ml_enhanced' in components:
                    print(f"  ML фактор: {components.get('ml_factor', 1.0):.3f}")
        else:
            print("❌ Победитель не выбран")
        
        # Очистка кэша
        self.feature_cache.clear_expired()
        
        return scored
    
    def _collect_candidates(self) -> List[SignalCandidate]:
        """Сбор кандидатов (заглушка для примера)."""
        # Здесь должна быть существующая логика сбора кандидатов
        return []
    
    def _get_forecasts(self, candidates: List[SignalCandidate]) -> List[FirstHitForecast]:
        """Получение прогнозов (заглушка для примера)."""
        # Здесь должна быть существующая логика прогнозирования
        return []
    
    def _get_btc_weight(self) -> float:
        """Получение BTC веса (заглушка для примера)."""
        # Здесь должна быть существующая логика получения BTC контекста
        return 0.5


def integrate_ml_in_existing_pipeline():
    """
    Пример интеграции ML в существующий пайплайн.
    Показывает минимальные изменения для добавления ML функциональности.
    """
    
    # В orchestrator/engine/pipeline.py
    # Замените существующий код на:
    
    print("🔧 Интеграция ML в существующий пайплайн...")
    
    # 1. Добавьте импорты
    from orchestrator.auction.scorer import MLConfig
    from orchestrator.engine.feature_cache import get_feature_cache
    
    # 2. В __init__ добавьте ML конфигурацию
    ml_config = MLConfig(
        enabled=settings.get("ml", {}).get("enabled", True),
        model_path=settings.get("ml", {}).get("model_path"),
        calibrator_prefer=settings.get("ml", {}).get("calibrator_prefer"),
        prob_weight_base=settings.get("ml", {}).get("prob_weight_base", 1.0),
        prob_weight_gain=settings.get("ml", {}).get("prob_weight_gain", 1.0)
    )
    
    # 3. В run_once() замените вызов score_candidates
    # Было:
    # scored = score_candidates(all_cands, forecasts, btc_weight)
    
    # Стало:
    ohlc_data = {}
    for symbol in self.symbols:
        try:
            bars = fetch_ohlcv_1h(symbol, limit=220)
            frows = build_feature_rows(bars)
            ohlc_data[symbol] = pd.DataFrame(frows)
        except Exception:
            ohlc_data[symbol] = pd.DataFrame()
    
    scored = score_candidates(
        all_cands, forecasts, btc_weight, 
        ml_cfg=ml_config, 
        ohlc_1h_by_symbol=ohlc_data
    )
    
    print("✅ ML интеграция завершена")


def test_ml_integration():
    """Тестирование ML интеграции."""
    print("🧪 Тестирование ML интеграции...")
    
    # Тестовые настройки
    settings = {
        "ml": {
            "enabled": True,
            "model_path": "forecast/models/binary_hit_ADAUSDT_and_6_more_H24.joblib",
            "calibrator_prefer": "isotonic",
            "prob_weight_base": 1.0,
            "prob_weight_gain": 1.0,
            "performance": {
                "cache_ttl_seconds": 300
            }
        }
    }
    
    # Создание пайплайна
    pipeline = EnhancedAnalyzePipeline(["ADAUSDT", "LTCUSDT"], settings)
    
    # Запуск цикла
    try:
        scored = pipeline.run_once()
        print(f"✅ Тест пройден: {len(scored)} кандидатов скорировано")
        return True
    except Exception as e:
        print(f"❌ Тест провален: {e}")
        return False


if __name__ == "__main__":
    # Демонстрация интеграции
    print("🚀 Демонстрация ML интеграции")
    print("=" * 50)
    
    # Тестирование
    success = test_ml_integration()
    
    if success:
        print("🎉 ML интеграция работает корректно!")
    else:
        print("⚠️  Требуется доработка ML интеграции")
    
    # Показ примера интеграции
    print("\n📋 Пример интеграции в существующий код:")
    integrate_ml_in_existing_pipeline()
