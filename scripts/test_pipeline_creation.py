#!/usr/bin/env python3
"""
Тест создания пайплайна после исправлений конфигурационных лоадеров.
"""

import sys
import os
sys.path.append('.')

def test_pipeline_creation():
    """Тест создания пайплайна с исправленными лоадерами."""
    print("🧪 ТЕСТ СОЗДАНИЯ ПАЙПЛАЙНА")
    print("=" * 50)
    
    # 1. Тест загрузки настроек
    print("1. Тест загрузки настроек...")
    try:
        from config.loader import load_settings
        settings = load_settings()
        print(f"   ✅ Настройки загружены")
        print(f"   ✅ Engine: {bool(settings.engine)}")
        print(f"   ✅ BTC Context: {bool(settings.btc_context)}")
        print(f"   ✅ ML: {bool(settings.ml)}")
        
        if settings.ml:
            print(f"   ✅ ML секция найдена: {list(settings.ml.keys())}")
        else:
            print("   ⚠️ ML секция пустая (используются дефолты)")
            
    except Exception as e:
        print(f"   ❌ Ошибка загрузки настроек: {e}")
        return False
    
    # 2. Тест загрузки символов
    print("2. Тест загрузки символов...")
    try:
        from config.loader import load_symbols
        symbols = load_symbols()
        print(f"   ✅ Символы загружены: {len(symbols.symbols)} символов")
        
        if symbols.symbols:
            print(f"   ✅ Первый символ: {symbols.symbols[0]}")
            print(f"   ✅ Последний символ: {symbols.symbols[-1]}")
        else:
            print("   ⚠️ Список символов пустой")
            
    except Exception as e:
        print(f"   ❌ Ошибка загрузки символов: {e}")
        return False
    
    # 3. Тест создания реестра моделей
    print("3. Тест создания реестра моделей...")
    try:
        from orchestrator.forecast.registry import PerSignalRegistry
        registry = PerSignalRegistry(settings)
        print(f"   ✅ Реестр моделей создан")
        print(f"   ✅ Per-signal карта: {bool(registry._map)}")
        print(f"   ✅ Fallback карта: {bool(registry._fallback)}")
        
    except Exception as e:
        print(f"   ❌ Ошибка создания реестра: {e}")
        return False
    
    # 4. Тест создания простого пайплайна
    print("4. Тест создания простого пайплайна...")
    try:
        from orchestrator.engine.pipeline import create_simple_pipeline
        pipeline = create_simple_pipeline(settings)
        print(f"   ✅ Пайплайн создан")
        print(f"   ✅ Символы: {pipeline.symbols}")
        print(f"   ✅ Провайдеры: {len(pipeline.providers)}")
        print(f"   ✅ Реестр моделей: {bool(pipeline.forecast_reg)}")
        
    except Exception as e:
        print(f"   ❌ Ошибка создания пайплайна: {e}")
        return False
    
    # 5. Тест инициализации брокера
    print("5. Тест инициализации брокера...")
    try:
        from orchestrator.exec.dummy_broker import DummyBroker
        from orchestrator.data.ingest import set_data_source
        
        broker = DummyBroker()
        set_data_source(broker)
        print(f"   ✅ Брокер инициализирован")
        print(f"   ✅ Источник данных установлен")
        
    except Exception as e:
        print(f"   ❌ Ошибка инициализации брокера: {e}")
        return False
    
    # 6. Тест одного цикла пайплайна
    print("6. Тест одного цикла пайплайна...")
    try:
        # Устанавливаем брокер для data ingest
        from orchestrator.data.ingest import set_data_source
        from orchestrator.exec.dummy_broker import DummyBroker
        
        broker = DummyBroker()
        set_data_source(broker)
        
        # Запускаем один цикл
        pipeline.run_once()
        print(f"   ✅ Цикл пайплайна выполнен")
        
    except Exception as e:
        print(f"   ❌ Ошибка выполнения цикла: {e}")
        return False
    
    print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("✅ Пайплайн создается и работает корректно")
    return True

if __name__ == "__main__":
    success = test_pipeline_creation()
    sys.exit(0 if success else 1)
