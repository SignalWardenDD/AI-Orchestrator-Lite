#!/usr/bin/env python3
"""
Тест per-signal моделей.
"""

import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.append('.')

def test_signal_types():
    """Тест констант типов сигналов."""
    print("🔍 Тестирование констант типов сигналов...")
    
    try:
        from orchestrator.signals.types import SIGNAL_TYPES, DEFAULT_HORIZONS, SIGNAL_TO_PROVIDER
        
        # Проверяем типы сигналов
        assert SIGNAL_TYPES == ("BRK", "PB", "MR", "BB"), f"Expected BRK,PB,MR,BB, got {SIGNAL_TYPES}"
        print("  ✅ SIGNAL_TYPES корректны")
        
        # Проверяем горизонты
        assert DEFAULT_HORIZONS == ("H12", "H24"), f"Expected H12,H24, got {DEFAULT_HORIZONS}"
        print("  ✅ DEFAULT_HORIZONS корректны")
        
        # Проверяем маппинг
        assert SIGNAL_TO_PROVIDER["BRK"] == "BreakoutProvider", "BRK should map to BreakoutProvider"
        assert SIGNAL_TO_PROVIDER["PB"] == "PullbackMRProvider", "PB should map to PullbackMRProvider"
        assert SIGNAL_TO_PROVIDER["MR"] == "PullbackMRProvider", "MR should map to PullbackMRProvider"
        assert SIGNAL_TO_PROVIDER["BB"] == "BollingerPlayProvider", "BB should map to BollingerPlayProvider"
        print("  ✅ SIGNAL_TO_PROVIDER маппинг корректен")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Signal types: {e}")
        return False

def test_utils():
    """Тест утилит."""
    print("\n🔍 Тестирование утилит...")
    
    try:
        from orchestrator.utils.seed import set_seed
        from orchestrator.utils.io import ensure_dir
        
        # Тест set_seed
        set_seed(42)
        print("  ✅ set_seed работает")
        
        # Тест ensure_dir
        test_dir = Path("test_temp_dir")
        ensure_dir(test_dir)
        assert test_dir.exists(), "Directory should be created"
        test_dir.rmdir()  # cleanup
        print("  ✅ ensure_dir работает")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Utils: {e}")
        return False

def test_data_loader():
    """Тест загрузчика данных."""
    print("\n🔍 Тестирование загрузчика данных...")
    
    try:
        from orchestrator.data.loader import load_features_df, load_kline_df, load_signal_marks_df
        
        # Проверяем, что функции импортируются
        print("  ✅ Функции загрузчика импортированы")
        
        # Тест с фиктивными данными (если есть)
        try:
            # Попробуем загрузить данные для ADAUSDT
            features = load_features_df("ADAUSDT")
            print(f"  ✅ Features loaded: {len(features)} rows")
        except FileNotFoundError:
            print("  ⚠️  Features not found (expected for test)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Data loader: {e}")
        return False

def test_calibration():
    """Тест калибровки."""
    print("\n🔍 Тестирование калибровки...")
    
    try:
        from orchestrator.forecast.calibration import fit_isotonic
        import numpy as np
        
        # Создаем тестовые данные
        np.random.seed(42)
        raw_scores = np.random.random(100)
        y_true = (raw_scores > 0.5).astype(int)
        
        # Тест калибровки
        calib = fit_isotonic(raw_scores, y_true)
        assert hasattr(calib, 'predict'), "Calibrator should have predict method"
        print("  ✅ fit_isotonic работает")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Calibration: {e}")
        return False

def test_labeling():
    """Тест создания лейблов."""
    print("\n🔍 Тестирование создания лейблов...")
    
    try:
        from orchestrator.forecast.labeling import make_binary_hit_labels
        import pandas as pd
        import numpy as np
        
        # Создаем тестовые OHLCV данные
        dates = pd.date_range('2023-01-01', periods=100, freq='H')
        np.random.seed(42)
        df = pd.DataFrame({
            'open': 100 + np.random.randn(100).cumsum(),
            'high': 100 + np.random.randn(100).cumsum() + 1,
            'low': 100 + np.random.randn(100).cumsum() - 1,
            'close': 100 + np.random.randn(100).cumsum(),
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
        
        # Тест создания лейблов
        labels = make_binary_hit_labels(df, "H12")
        assert len(labels) == len(df), f"Labels length {len(labels)} != data length {len(df)}"
        assert labels.dtype in [int, float], f"Labels should be numeric, got {labels.dtype}"
        print(f"  ✅ Labels created: {len(labels)} rows, {labels.sum()} hits")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Labeling: {e}")
        return False

def test_registry():
    """Тест реестра моделей."""
    print("\n🔍 Тестирование реестра моделей...")
    
    try:
        from orchestrator.forecast.registry import PerSignalRegistry
        
        # Создаем мок конфигурацию
        class MockConfig:
            class ml:
                class models_per_signal:
                    yaml_path = "config/models_per_signal.yaml"
                class models_individual:
                    yaml_path = "config/models_individual_optimized.yaml"
        
        # Тест создания реестра
        registry = PerSignalRegistry(MockConfig())
        print("  ✅ PerSignalRegistry создан")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Registry: {e}")
        return False

def test_scripts():
    """Тест скриптов."""
    print("\n🔍 Тестирование скриптов...")
    
    try:
        # Проверяем, что скрипты существуют
        scripts = [
            "scripts/train_forecasters_per_signal.py",
            "scripts/calibrate_per_signal.py", 
            "scripts/gen_models_yaml_per_signal.py"
        ]
        
        for script in scripts:
            assert Path(script).exists(), f"Script {script} not found"
            print(f"  ✅ {script} существует")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Scripts: {e}")
        return False

def test_makefile():
    """Тест Makefile."""
    print("\n🔍 Тестирование Makefile...")
    
    try:
        # Проверяем, что Makefile содержит per-signal цели
        with open("Makefile", "r") as f:
            content = f.read()
        
        required_targets = [
            "train-per-signal:",
            "calibrate-per-signal:",
            "gen-yaml-per-signal:",
            "per-signal-all:"
        ]
        
        for target in required_targets:
            assert target in content, f"Target {target} not found in Makefile"
            print(f"  ✅ {target} найден в Makefile")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Makefile: {e}")
        return False

def main():
    """Главная функция тестирования per-signal моделей."""
    print("🚀 ТЕСТИРОВАНИЕ PER-SIGNAL МОДЕЛЕЙ")
    print("=" * 60)
    print("Проверка инфраструктуры для per-signal моделей")
    print("=" * 60)
    
    tests = [
        test_signal_types,
        test_utils,
        test_data_loader,
        test_calibration,
        test_labeling,
        test_registry,
        test_scripts,
        test_makefile
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Тест {test.__name__} упал: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ PER-SIGNAL МОДЕЛЕЙ:")
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"  {i+1}. {test.__name__}: {status}")
    
    print(f"\n🎯 ИТОГО: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 PER-SIGNAL ИНФРАСТРУКТУРА ГОТОВА!")
        print("✅ Константы и типы сигналов")
        print("✅ Утилиты для работы с данными")
        print("✅ Загрузчик данных")
        print("✅ Калибровка моделей")
        print("✅ Создание лейблов")
        print("✅ Реестр моделей")
        print("✅ Скрипты обучения")
        print("✅ Makefile цели")
        return True
    else:
        print("⚠️  ЕСТЬ ПРОБЛЕМЫ В PER-SIGNAL ИНФРАСТРУКТУРЕ!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
