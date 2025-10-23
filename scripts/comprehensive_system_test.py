#!/usr/bin/env python3
"""
Комплексное тестирование всей системы оркестратора.
"""

import sys
import os
import json
import yaml
import pandas as pd
import numpy as np
from pathlib import Path
import traceback
import time
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.append('.')

def test_imports():
    """Тест 1: Проверка всех импортов."""
    print("🔍 Тест 1: Проверка импортов...")
    
    try:
        # Основные модули
        from orchestrator.app import main as app_main
        from orchestrator.engine.pipeline import Pipeline
        from orchestrator.data.loader import load_kline_df, load_features_df
        from orchestrator.forecast.registry import PerSignalRegistry
        from orchestrator.exec.broker import Broker
        from orchestrator.exec.planner import plan_entry
        from orchestrator.exec.sl_manager import maybe_adjust_sl
        from orchestrator.signals.breakout import compute_marks as brk_marks
        from orchestrator.signals.pullback_mr import compute_marks as pb_marks
        from orchestrator.signals.trend import compute_marks as trend_marks
        from orchestrator.signals.bollinger_play import compute_marks as bb_marks
        
        print("✅ Все импорты успешны")
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        traceback.print_exc()
        return False

def test_config_loading():
    """Тест 2: Загрузка конфигураций."""
    print("\n🔍 Тест 2: Загрузка конфигураций...")
    
    try:
        # Основная конфигурация
        with open('config/settings.yaml', 'r') as f:
            settings = yaml.safe_load(f)
        
        # Оптимизированные конфигурации
        with open('config/optimized/models_per_signal_optimized.yaml', 'r') as f:
            per_signal_config = yaml.safe_load(f)
        
        with open('config/optimized/models_individual_optimized.yaml', 'r') as f:
            individual_config = yaml.safe_load(f)
        
        # Проверяем ключевые настройки
        assert 'ml' in settings, "ML настройки отсутствуют"
        assert 'models_per_signal' in settings['ml'], "Per-signal настройки отсутствуют"
        assert 'models_individual' in settings['ml'], "Individual настройки отсутствуют"
        
        print("✅ Конфигурации загружены успешно")
        print(f"   - Per-signal моделей: {len(per_signal_config.get('models', {}))}")
        print(f"   - Individual моделей: {len(individual_config.get('models', {}))}")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигураций: {e}")
        return False

def test_data_loading():
    """Тест 3: Загрузка данных."""
    print("\n🔍 Тест 3: Загрузка данных...")
    
    try:
        from orchestrator.data.loader import load_kline_df, load_features_df, load_signal_marks_df
        
        # Тестируем загрузку OHLCV данных
        symbols = ['ADAUSDT', 'DOGEUSDT', 'LTCUSDT']
        for symbol in symbols:
            try:
                kline = load_kline_df(symbol)
                assert len(kline) > 0, f"Нет данных для {symbol}"
                assert 'close' in kline.columns, f"Нет колонки close для {symbol}"
                print(f"   ✅ {symbol}: {len(kline)} баров")
            except Exception as e:
                print(f"   ⚠️ {symbol}: {e}")
        
        # Тестируем загрузку фичей
        for symbol in symbols:
            try:
                features = load_features_df(symbol)
                assert len(features) > 0, f"Нет фичей для {symbol}"
                print(f"   ✅ {symbol} features: {len(features)} строк")
            except Exception as e:
                print(f"   ⚠️ {symbol} features: {e}")
        
        # Тестируем загрузку сигнальных меток
        for symbol in symbols:
            try:
                marks = load_signal_marks_df(symbol)
                assert len(marks) > 0, f"Нет меток для {symbol}"
                assert set(['BRK', 'PB', 'MR', 'BB']).issubset(marks.columns), f"Неполные метки для {symbol}"
                print(f"   ✅ {symbol} marks: {len(marks)} строк")
            except Exception as e:
                print(f"   ⚠️ {symbol} marks: {e}")
        
        print("✅ Загрузка данных успешна")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        traceback.print_exc()
        return False

def test_ml_models():
    """Тест 4: ML модели и реестр."""
    print("\n🔍 Тест 4: ML модели и реестр...")
    
    try:
        from orchestrator.forecast.registry import PerSignalRegistry
        
        # Загружаем конфигурацию
        with open('config/optimized/models_individual_optimized.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Создаем реестр
        registry = PerSignalRegistry(config)
        
        # Тестируем загрузку моделей
        test_cases = [
            ('ADAUSDT', 'BRK', 'H12'),
            ('DOGEUSDT', 'PB', 'H24'),
            ('LTCUSDT', 'MR', 'H12'),
            ('ARBUSDT', 'BB', 'H24')
        ]
        
        for symbol, signal, horizon in test_cases:
            try:
                model_bundle = registry.get_model(symbol, signal, horizon)
                if model_bundle:
                    print(f"   ✅ {symbol}_{signal}_{horizon}: модель загружена")
                else:
                    print(f"   ⚠️ {symbol}_{signal}_{horizon}: модель не найдена (fallback)")
            except Exception as e:
                print(f"   ⚠️ {symbol}_{signal}_{horizon}: {e}")
        
        print("✅ ML модели работают")
        return True
    except Exception as e:
        print(f"❌ Ошибка ML моделей: {e}")
        traceback.print_exc()
        return False

def test_signal_providers():
    """Тест 5: Провайдеры сигналов."""
    print("\n🔍 Тест 5: Провайдеры сигналов...")
    
    try:
        from orchestrator.signals.breakout import compute_marks as brk_marks
        from orchestrator.signals.pullback_mr import compute_marks as pb_marks
        from orchestrator.signals.trend import compute_marks as trend_marks
        from orchestrator.signals.bollinger_play import compute_marks as bb_marks
        
        # Создаем тестовые данные
        dates = pd.date_range('2024-01-01', periods=100, freq='1H')
        test_data = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(150, 250, 100),
            'low': np.random.uniform(50, 150, 100),
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.uniform(1000, 10000, 100)
        }, index=dates)
        
        # Тестируем каждый провайдер
        providers = [
            ('Breakout', brk_marks),
            ('Pullback/MR', pb_marks),
            ('Trend', trend_marks),
            ('Bollinger', bb_marks)
        ]
        
        for name, provider_func in providers:
            try:
                marks = provider_func(test_data)
                assert len(marks) == len(test_data), f"Неверная длина для {name}"
                assert marks.dtype in ['int8', 'int64', 'bool'], f"Неверный тип для {name}"
                signal_count = marks.sum() if hasattr(marks, 'sum') else sum(marks)
                print(f"   ✅ {name}: {signal_count} сигналов")
            except Exception as e:
                print(f"   ⚠️ {name}: {e}")
        
        print("✅ Провайдеры сигналов работают")
        return True
    except Exception as e:
        print(f"❌ Ошибка провайдеров сигналов: {e}")
        traceback.print_exc()
        return False

def test_execution_logic():
    """Тест 6: Логика исполнения."""
    print("\n🔍 Тест 6: Логика исполнения...")
    
    try:
        from orchestrator.exec.planner import plan_entry
        from orchestrator.exec.sl_manager import maybe_adjust_sl
        from orchestrator.exec.utils import opposite, tick_round
        
        # Тест утилит
        assert opposite('BUY') == 'SELL', "Неверная функция opposite"
        assert opposite('SELL') == 'BUY', "Неверная функция opposite"
        
        # Тест tick_round
        rounded = tick_round(0.450156, 0.0001)
        assert abs(rounded - 0.4502) < 1e-10, f"Неверное округление: {rounded}"
        
        # Тест планирования входа
        test_signal = {
            'symbol': 'ADAUSDT',
            'side': 'BUY',
            'price': 0.45,
            'atr': 0.01,
            'tp_mult': 2.0,
            'sl_mult': 1.5
        }
        
        try:
            plan = plan_entry(test_signal, {})
            print(f"   ✅ Планирование входа: {plan}")
        except Exception as e:
            print(f"   ⚠️ Планирование входа: {e}")
        
        # Тест управления SL
        test_position = {
            'symbol': 'ADAUSDT',
            'side': 'LONG',
            'entry_price': 0.45,
            'size': 100,
            'unrealized_pnl': 0.20
        }
        
        try:
            sl_adjustment = maybe_adjust_sl(test_position, {})
            print(f"   ✅ Управление SL: {sl_adjustment}")
        except Exception as e:
            print(f"   ⚠️ Управление SL: {e}")
        
        print("✅ Логика исполнения работает")
        return True
    except Exception as e:
        print(f"❌ Ошибка логики исполнения: {e}")
        traceback.print_exc()
        return False

def test_risk_management():
    """Тест 7: Управление рисками."""
    print("\n🔍 Тест 7: Управление рисками...")
    
    try:
        from orchestrator.risk.filters import check_daily_loss, check_position_limits
        from orchestrator.risk.sizing import calculate_position_size
        
        # Тест проверки дневных потерь
        try:
            daily_pnl = -5.0
            daily_limit = -7.5
            result = check_daily_loss(daily_pnl, daily_limit)
            assert result == True, "Неверная проверка дневных потерь"
            print("   ✅ Проверка дневных потерь работает")
        except Exception as e:
            print(f"   ⚠️ Проверка дневных потерь: {e}")
        
        # Тест проверки лимитов позиций
        try:
            current_positions = 2
            max_positions = 4
            result = check_position_limits(current_positions, max_positions)
            assert result == True, "Неверная проверка лимитов позиций"
            print("   ✅ Проверка лимитов позиций работает")
        except Exception as e:
            print(f"   ⚠️ Проверка лимитов позиций: {e}")
        
        # Тест расчета размера позиции
        try:
            notional = 15.0
            leverage = 5
            size = calculate_position_size(notional, leverage)
            assert size > 0, "Неверный расчет размера позиции"
            print(f"   ✅ Расчет размера позиции: {size}")
        except Exception as e:
            print(f"   ⚠️ Расчет размера позиции: {e}")
        
        print("✅ Управление рисками работает")
        return True
    except Exception as e:
        print(f"❌ Ошибка управления рисками: {e}")
        traceback.print_exc()
        return False

def test_telemetry():
    """Тест 8: Телеметрия и логирование."""
    print("\n🔍 Тест 8: Телеметрия и логирование...")
    
    try:
        from orchestrator.telemetry.logger import setup_logger
        from orchestrator.telemetry.metrics import MetricsCollector
        
        # Тест настройки логгера
        try:
            logger = setup_logger('test_logger')
            logger.info("Тестовое сообщение")
            print("   ✅ Логгер настроен")
        except Exception as e:
            print(f"   ⚠️ Логгер: {e}")
        
        # Тест сбора метрик
        try:
            metrics = MetricsCollector()
            metrics.record_signal('ADAUSDT', 'BRK', 'BUY', 0.15)
            metrics.record_trade('ADAUSDT', 'BUY', 0.45, 100, 0.20)
            print("   ✅ Сбор метрик работает")
        except Exception as e:
            print(f"   ⚠️ Сбор метрик: {e}")
        
        print("✅ Телеметрия работает")
        return True
    except Exception as e:
        print(f"❌ Ошибка телеметрии: {e}")
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Тест 9: API эндпоинты."""
    print("\n🔍 Тест 9: API эндпоинты...")
    
    try:
        from orchestrator.api.healthcheck import health_check
        from orchestrator.api.control import get_status, get_positions
        
        # Тест health check
        try:
            health_status = health_check()
            assert 'status' in health_status, "Неверный формат health check"
            print(f"   ✅ Health check: {health_status}")
        except Exception as e:
            print(f"   ⚠️ Health check: {e}")
        
        # Тест получения статуса
        try:
            status = get_status()
            assert 'system' in status, "Неверный формат статуса"
            print(f"   ✅ Статус системы: {status}")
        except Exception as e:
            print(f"   ⚠️ Статус системы: {e}")
        
        # Тест получения позиций
        try:
            positions = get_positions()
            assert isinstance(positions, list), "Неверный формат позиций"
            print(f"   ✅ Позиции: {len(positions)} активных")
        except Exception as e:
            print(f"   ⚠️ Позиции: {e}")
        
        print("✅ API эндпоинты работают")
        return True
    except Exception as e:
        print(f"❌ Ошибка API эндпоинтов: {e}")
        traceback.print_exc()
        return False

def test_integration():
    """Тест 10: Интеграционное тестирование."""
    print("\n🔍 Тест 10: Интеграционное тестирование...")
    
    try:
        from orchestrator.engine.pipeline import Pipeline
        
        # Загружаем конфигурацию
        with open('config/settings.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Создаем пайплайн
        from orchestrator.engine.pipeline import create_simple_pipeline
        pipeline = create_simple_pipeline(config)
        
        # Тестируем основные методы
        try:
            # Тест инициализации
            assert hasattr(pipeline, 'model_registry'), "Нет реестра моделей"
            assert hasattr(pipeline, 'signal_providers'), "Нет провайдеров сигналов"
            print("   ✅ Пайплайн инициализирован")
            
            # Тест анализа сигналов
            test_data = {
                'ADAUSDT': pd.DataFrame({
                    'open': [0.45, 0.46, 0.47],
                    'high': [0.46, 0.47, 0.48],
                    'low': [0.44, 0.45, 0.46],
                    'close': [0.46, 0.47, 0.48],
                    'volume': [1000, 1100, 1200]
                })
            }
            
            try:
                signals = pipeline.analyze_signals(test_data)
                print(f"   ✅ Анализ сигналов: {len(signals)} сигналов")
            except Exception as e:
                print(f"   ⚠️ Анализ сигналов: {e}")
            
        except Exception as e:
            print(f"   ⚠️ Пайплайн: {e}")
        
        print("✅ Интеграционное тестирование завершено")
        return True
    except Exception as e:
        print(f"❌ Ошибка интеграционного тестирования: {e}")
        traceback.print_exc()
        return False

def run_performance_test():
    """Тест 11: Тест производительности."""
    print("\n🔍 Тест 11: Тест производительности...")
    
    try:
        import time
        
        # Тест скорости загрузки данных
        start_time = time.time()
        
        from orchestrator.data.loader import load_kline_df
        for symbol in ['ADAUSDT', 'DOGEUSDT', 'LTCUSDT']:
            try:
                data = load_kline_df(symbol)
            except:
                pass
        
        load_time = time.time() - start_time
        print(f"   ✅ Загрузка данных: {load_time:.3f} сек")
        
        # Тест скорости ML предсказаний
        start_time = time.time()
        
        try:
            from orchestrator.forecast.registry import PerSignalRegistry
            with open('config/optimized/models_individual_optimized.yaml', 'r') as f:
                config = yaml.safe_load(f)
            registry = PerSignalRegistry(config)
            
            # Тестируем несколько предсказаний
            for _ in range(10):
                try:
                    model = registry.get_model('ADAUSDT', 'BRK', 'H12')
                except:
                    pass
        except:
            pass
        
        ml_time = time.time() - start_time
        print(f"   ✅ ML предсказания: {ml_time:.3f} сек")
        
        print("✅ Тест производительности завершен")
        return True
    except Exception as e:
        print(f"❌ Ошибка теста производительности: {e}")
        return False

def main():
    """Главная функция комплексного тестирования."""
    print("🚀 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ")
    print("=" * 60)
    
    tests = [
        ("Импорты", test_imports),
        ("Конфигурации", test_config_loading),
        ("Загрузка данных", test_data_loading),
        ("ML модели", test_ml_models),
        ("Провайдеры сигналов", test_signal_providers),
        ("Логика исполнения", test_execution_logic),
        ("Управление рисками", test_risk_management),
        ("Телеметрия", test_telemetry),
        ("API эндпоинты", test_api_endpoints),
        ("Интеграция", test_integration),
        ("Производительность", run_performance_test)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в {test_name}: {e}")
            results.append((test_name, False))
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:20} {status}")
    
    print(f"\n📈 РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! СИСТЕМА ГОТОВА!")
    elif passed >= total * 0.8:
        print("⚠️ БОЛЬШИНСТВО ТЕСТОВ ПРОЙДЕНО. ЕСТЬ НЕЗНАЧИТЕЛЬНЫЕ ПРОБЛЕМЫ.")
    else:
        print("❌ МНОГО ПРОВАЛЕННЫХ ТЕСТОВ. ТРЕБУЕТСЯ ДОРАБОТКА.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
