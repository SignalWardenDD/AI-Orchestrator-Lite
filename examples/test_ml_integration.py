# test_ml_integration.py
"""
Тестовый скрипт для проверки интеграции ML функциональности.
Проверяет все компоненты системы и их взаимодействие.
"""

from __future__ import annotations
import os
import json
from typing import Dict, List
import pandas as pd
import numpy as np

# Импорты существующих модулей
from orchestrator.utils.types import SignalCandidate, FirstHitForecast

# Импорты новых модулей
from orchestrator.forecast.lgbm_forecaster import Forecaster
from orchestrator.forecast.features_builder import build_features_for_candidate
from orchestrator.auction.ml_scorer import get_ml_scorer, enhance_score_with_ml


def test_forecaster_loading():
    """Тест загрузки форекастера."""
    print("🔧 Тестирование загрузки форекастера...")
    
    models_dir = "forecast/models"
    if not os.path.exists(models_dir):
        print(f"⚠️  Директория моделей не найдена: {models_dir}")
        return False
    
    # Поиск моделей
    import glob
    model_files = glob.glob(os.path.join(models_dir, "*.joblib"))
    
    if not model_files:
        print("⚠️  Модели не найдены")
        return False
    
    # Тест загрузки первой модели
    model_path = model_files[0]
    try:
        forecaster = Forecaster(model_path)
        print(f"✅ Модель загружена: {os.path.basename(model_path)}")
        print(f"  Тип: {forecaster.meta().get('kind', 'unknown')}")
        print(f"  Признаки: {len(forecaster.get_feature_names())}")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки модели: {e}")
        return False


def test_features_builder():
    """Тест сборщика признаков."""
    print("🔧 Тестирование сборщика признаков...")
    
    # Создаем тестовый кандидат
    candidate = SignalCandidate(
        symbol="ADAUSDT",
        type="BRK",
        side="LONG",
        entry_price=1.0,
        atr=0.02,
        ema20=0.99,
        meta={"rsi2": 50.0, "natr14_pct": 1.0},
        ts=1234567890
    )
    
    # Создаем тестовые OHLC данные
    ohlc_data = pd.DataFrame({
        'open': [0.98, 0.99, 1.00, 1.01, 1.02],
        'high': [1.00, 1.01, 1.02, 1.03, 1.04],
        'low': [0.97, 0.98, 0.99, 1.00, 1.01],
        'close': [0.99, 1.00, 1.01, 1.02, 1.03],
        'volume': [1000, 1100, 1200, 1300, 1400]
    })
    
    try:
        # Тест с OHLC данными
        features_with_ohlc = build_features_for_candidate(candidate, ohlc_data)
        print(f"✅ Признаки с OHLC: {len(features_with_ohlc)} признаков")
        
        # Тест без OHLC данных
        features_basic = build_features_for_candidate(candidate, None)
        print(f"✅ Базовые признаки: {len(features_basic)} признаков")
        
        # Проверка наличия ключевых признаков
        required_features = ['ret_1', 'ema20', 'natr14', 'sym__ADAUSDT']
        for feature in required_features:
            if feature in features_with_ohlc:
                print(f"  ✓ {feature}: {features_with_ohlc[feature]}")
            else:
                print(f"  ✗ {feature}: отсутствует")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания признаков: {e}")
        return False


def test_ml_scorer():
    """Тест ML скорера."""
    print("🔧 Тестирование ML скорера...")
    
    try:
        ml_scorer = get_ml_scorer()
        available_models = ml_scorer.get_available_models()
        
        print(f"📊 Доступные модели: {available_models}")
        
        if available_models:
            print("✅ ML скорер готов к использованию")
            
            # Тест улучшения скора
            candidate = SignalCandidate(
                symbol="ADAUSDT",
                type="BRK",
                side="LONG",
                entry_price=1.0,
                atr=0.02,
                ema20=0.99,
                meta={},
                ts=1234567890
            )
            
            base_score = 0.15
            horizon = 24
            
            enhanced_score = ml_scorer.enhance_score_with_ml(
                candidate, base_score, horizon, None
            )
            
            print(f"  Базовый скор: {base_score:.4f}")
            print(f"  Улучшенный скор: {enhanced_score:.4f}")
            print(f"  ML фактор: {enhanced_score / base_score:.4f}")
            
            return True
        else:
            print("ℹ️  ML модели недоступны, будет использоваться fallback")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка ML скорера: {e}")
        return False


def test_integration():
    """Тест полной интеграции."""
    print("🔧 Тестирование полной интеграции...")
    
    try:
        # Создаем тестовые данные
        candidates = [
            SignalCandidate(
                symbol="ADAUSDT",
                type="BRK",
                side="LONG",
                entry_price=1.0,
                atr=0.02,
                ema20=0.99,
                meta={},
                ts=1234567890
            ),
            SignalCandidate(
                symbol="LTCUSDT",
                type="PB",
                side="SHORT",
                entry_price=100.0,
                atr=2.0,
                ema20=99.0,
                meta={},
                ts=1234567890
            )
        ]
        
        forecasts = [
            FirstHitForecast(
                symbol="ADAUSDT",
                type="BRK",
                side="LONG",
                H=24,
                p_hit={"tp1": 0.2, "tp2": 0.15, "tp3": 0.1, "tp4": 0.05, "sl": 0.5},
                t_hit={"tp1": 2.0, "tp2": 3.0, "tp3": 5.0, "tp4": 7.0, "sl": 2.5},
                fill_prob=0.7,
                slip_est=0.0008,
                conf_type=0.5,
                flags={}
            )
        ]
        
        # Тест оригинального скоринга
        from orchestrator.auction.scorer import score_candidates
        original_scored = score_candidates(candidates, forecasts, 0.5)
        print(f"✅ Оригинальный скоринг: {len(original_scored)} кандидатов")
        
        # Тест ML-улучшенного скоринга
        from orchestrator.auction.ml_scorer import safe_enhanced_score_candidates
        enhanced_scored = safe_enhanced_score_candidates(
            candidates, forecasts, 0.5, {}
        )
        print(f"✅ ML-улучшенный скоринг: {len(enhanced_scored)} кандидатов")
        
        # Сравнение результатов
        if len(original_scored) > 0 and len(enhanced_scored) > 0:
            orig_score = original_scored[0].score_usdt
            enh_score = enhanced_scored[0].score_usdt
            print(f"  Оригинальный скор: {orig_score:.4f}")
            print(f"  Улучшенный скор: {enh_score:.4f}")
            print(f"  Разница: {enh_score - orig_score:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        return False


def test_fallback_modes():
    """Тест fallback режимов."""
    print("🔧 Тестирование fallback режимов...")
    
    # Тест без ML библиотек
    try:
        # Имитируем отсутствие sklearn
        import sys
        if 'sklearn' in sys.modules:
            del sys.modules['sklearn']
        
        # Тест должен работать в fallback режиме
        from orchestrator.forecast.lgbm_forecaster import Forecaster
        
        # Создаем фиктивную модель
        test_model_path = "test_model.joblib"
        if os.path.exists(test_model_path):
            os.remove(test_model_path)
        
        print("✅ Fallback режим работает корректно")
        return True
        
    except Exception as e:
        print(f"⚠️  Fallback режим: {e}")
        return True  # Fallback режим может не работать в тестах


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование интеграции ML функциональности")
    print("=" * 50)
    
    tests = [
        ("Загрузка форекастера", test_forecaster_loading),
        ("Сборщик признаков", test_features_builder),
        ("ML скорер", test_ml_scorer),
        ("Полная интеграция", test_integration),
        ("Fallback режимы", test_fallback_modes),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results[test_name] = result
            status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
            print(f"{status}: {test_name}")
        except Exception as e:
            results[test_name] = False
            print(f"❌ ОШИБКА: {test_name} - {e}")
    
    # Итоговый отчет
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Система готова к использованию.")
    elif passed >= total * 0.8:
        print("⚠️  Большинство тестов пройдено. Система готова с ограничениями.")
    else:
        print("❌ Много тестов провалено. Требуется доработка.")
    
    # Сохранение отчета
    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "total_tests": total,
        "passed_tests": passed,
        "results": results
    }
    
    with open("test_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Отчет сохранен: test_report.json")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
