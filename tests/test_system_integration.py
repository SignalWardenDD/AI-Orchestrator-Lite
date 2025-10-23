#!/usr/bin/env python3
"""
Полный тест системы перед лайвом.
Проверяет все модули, конфигурации и интеграцию.
"""

import sys
import os
import yaml
import traceback
from typing import Dict, Any, List

# Добавляем путь к проекту
sys.path.append('.')

def test_imports():
    """Тест импортов всех модулей."""
    print("🔍 Тестирование импортов...")
    
    modules = [
        'orchestrator.engine.pipeline',
        'orchestrator.auction.scorer',
        'orchestrator.exec.planner',
        'orchestrator.exec.broker',
        'orchestrator.exec.pnl',
        'orchestrator.exec.sl_manager',
        'orchestrator.risk.limits',
        'orchestrator.guards.microstructure',
        'orchestrator.forecast.lgbm_forecaster',
        'orchestrator.features.builder',
        'orchestrator.telemetry.logger',
        'orchestrator.state.store'
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module}: {e}")
            failed.append(module)
    
    if failed:
        print(f"❌ Неудачные импорты: {failed}")
        return False
    else:
        print("✅ Все импорты успешны")
        return True

def test_configs():
    """Тест конфигурационных файлов."""
    print("\n🔍 Тестирование конфигураций...")
    
    configs = [
        'config/settings.yaml',
        'config/symbols.yaml',
        'config/risk.yaml', 
        'config/ladders.yaml',
        'config/models_individual_optimized.yaml'
    ]
    
    failed = []
    for config in configs:
        if not os.path.exists(config):
            print(f"  ❌ {config} не найден")
            failed.append(config)
            continue
            
        try:
            with open(config, 'r') as f:
                yaml.safe_load(f)
            print(f"  ✅ {config}")
        except Exception as e:
            print(f"  ❌ {config}: {e}")
            failed.append(config)
    
    if failed:
        print(f"❌ Неудачные конфиги: {failed}")
        return False
    else:
        print("✅ Все конфиги валидны")
        return True

def test_ml_models():
    """Тест ML моделей."""
    print("\n🔍 Тестирование ML моделей...")
    
    models_dir = "forecast/models"
    if not os.path.exists(models_dir):
        print(f"❌ Директория {models_dir} не найдена")
        return False
    
    # Проверяем наличие моделей
    h12_models = [f for f in os.listdir(models_dir) if f.endswith('H12.joblib')]
    h24_models = [f for f in os.listdir(models_dir) if f.endswith('H24.joblib')]
    calibrators = [f for f in os.listdir(models_dir) if f.endswith('.calib.isotonic.joblib')]
    
    print(f"  📊 H12 моделей: {len(h12_models)}")
    print(f"  📊 H24 моделей: {len(h24_models)}")
    print(f"  📊 Калибраторов: {len(calibrators)}")
    
    if len(h12_models) < 10:
        print("⚠️  Мало H12 моделей")
    if len(h24_models) < 10:
        print("⚠️  Мало H24 моделей")
    if len(calibrators) < 20:
        print("⚠️  Мало калибраторов")
    
    print("✅ ML модели проверены")
    return True

def test_pnl_calculations():
    """Тест PnL вычислений."""
    print("\n🔍 Тестирование PnL вычислений...")
    
    try:
        from orchestrator.exec.pnl import unrealized_pnl_usd, compute_price_for_pnl
        
        # Тест unrealized_pnl_usd
        pnl_long = unrealized_pnl_usd(100.0, 105.0, 1.0, "LONG")
        assert pnl_long == 5.0, f"Ожидался 5.0, получен {pnl_long}"
        
        pnl_short = unrealized_pnl_usd(100.0, 95.0, 1.0, "SHORT")
        assert pnl_short == 5.0, f"Ожидался 5.0, получен {pnl_short}"
        
        # Тест compute_price_for_pnl
        price_long = compute_price_for_pnl(100.0, 1.0, "LONG", 5.0)
        assert price_long == 105.0, f"Ожидалась 105.0, получена {price_long}"
        
        price_short = compute_price_for_pnl(100.0, 1.0, "SHORT", 5.0)
        assert price_short == 95.0, f"Ожидалась 95.0, получена {price_short}"
        
        print("✅ PnL вычисления работают")
        return True
        
    except Exception as e:
        print(f"❌ PnL вычисления: {e}")
        return False

def test_ml_integration():
    """Тест ML интеграции."""
    print("\n🔍 Тестирование ML интеграции...")
    
    try:
        from orchestrator.auction.scorer import IndividualMLManager
        from orchestrator.features.builder import build_features_for_candidate
        import pandas as pd
        
        # Тест загрузки ML менеджера
        ml_manager = IndividualMLManager("config/models_individual_optimized.yaml")
        print(f"  📊 Активных символов: {len(ml_manager.get_available_symbols())}")
        print(f"  📊 Отключенных символов: {len(ml_manager.get_disabled_symbols())}")
        
        # Тест предсказания
        test_features = pd.DataFrame({
            'ret_1': [0.01],
            'ret_3': [0.02], 
            'ret_6': [0.03],
            'ema20': [100.0],
            'ema50': [99.0],
            'ema200': [98.0],
            'ema20_slope': [0.001],
            'natr14': [1.5],
            'rng_1': [0.02],
            'rng_3': [0.015],
            'z_close_50': [0.5],
            'ret_1_lag1': [0.005],
            'ret_1_lag2': [0.003],
            'ret_1_lag3': [0.002],
            'rng_1_lag1': [0.01],
            'rng_1_lag2': [0.008],
            'rng_1_lag3': [0.006]
        })
        
        # Тест для ADAUSDT
        if "ADAUSDT" in ml_manager.get_available_symbols():
            prob, meta = ml_manager.predict_ensemble("ADAUSDT", test_features)
            print(f"  📊 ADAUSDT предсказание: {prob:.3f}")
            print(f"  📊 Метаданные: {meta}")
        
        print("✅ ML интеграция работает")
        return True
        
    except Exception as e:
        print(f"❌ ML интеграция: {e}")
        traceback.print_exc()
        return False

def test_risk_limits():
    """Тест риск-лимитов."""
    print("\n🔍 Тестирование риск-лимитов...")
    
    try:
        from orchestrator.risk.limits import can_open_new_position, check_position_limits
        
        # Мок состояние
        class MockState:
            def __init__(self, positions_count=0, has_position=False, pending=False):
                self.positions_count = positions_count
                self.has_position = has_position
                self.pending = pending
            
            def open_positions_count(self):
                return self.positions_count
            
            def has_open_position(self, symbol):
                return self.has_position
            
            def pending_entry_for(self, symbol):
                return self.pending
        
        # Тест лимитов
        cfg = {"max_open_positions_global": 4, "max_open_positions_per_symbol": 1}
        
        # Тест 1: можно открыть
        state1 = MockState(positions_count=2, has_position=False, pending=False)
        can_open, reason = check_position_limits(state1, "BTCUSDT", cfg)
        assert can_open, f"Должно быть можно открыть: {reason}"
        
        # Тест 2: глобальный лимит
        state2 = MockState(positions_count=4, has_position=False, pending=False)
        can_open, reason = check_position_limits(state2, "BTCUSDT", cfg)
        assert not can_open, f"Должен быть заблокирован глобальный лимит: {reason}"
        
        # Тест 3: позиция уже открыта
        state3 = MockState(positions_count=2, has_position=True, pending=False)
        can_open, reason = check_position_limits(state3, "BTCUSDT", cfg)
        assert not can_open, f"Должен быть заблокирован дубликат: {reason}"
        
        print("✅ Риск-лимиты работают")
        return True
        
    except Exception as e:
        print(f"❌ Риск-лимиты: {e}")
        return False

def test_microstructure_guards():
    """Тест микроструктурных гвардов."""
    print("\n🔍 Тестирование микроструктурных гвардов...")
    
    try:
        from orchestrator.guards.microstructure import microstructure_edge_guard
        
        # Мок контекст
        class MockBar:
            def __init__(self, open, high, low, close):
                self.open = open
                self.high = high
                self.low = low
                self.close = close
        
        class MockCtx:
            def __init__(self):
                self.last_bar = {
                    "BTCUSDT": MockBar(100, 102, 99, 101)  # зеленая свеча
                }
                self.ind = type('obj', (object,), {
                    'rsi2': {"BTCUSDT": 50}
                })()
        
        ctx = MockCtx()
        
        # Тест нормальной ситуации
        blocked = microstructure_edge_guard(ctx, "BTCUSDT", "LONG")
        assert not blocked, "Нормальная ситуация не должна блокироваться"
        
        print("✅ Микроструктурные гварды работают")
        return True
        
    except Exception as e:
        print(f"❌ Микроструктурные гварды: {e}")
        return False

def main():
    """Главная функция тестирования."""
    print("🚀 ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ ПЕРЕД ЛАЙВОМ")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_configs,
        test_ml_models,
        test_pnl_calculations,
        test_ml_integration,
        test_risk_limits,
        test_microstructure_guards
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Тест {test.__name__} упал: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"  {i+1}. {test.__name__}: {status}")
    
    print(f"\n🎯 ИТОГО: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! СИСТЕМА ГОТОВА К ЛАЙВУ!")
        return True
    else:
        print("⚠️  ЕСТЬ ПРОБЛЕМЫ! НЕ ЗАПУСКАТЬ В ЛАЙВ!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
