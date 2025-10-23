#!/bin/bash
# Скрипт для запуска торговой системы с полными проверками

echo "🚀 ORCHESTRATOR-ALPHA v1.0 - ЗАПУСК ТОРГОВОЙ СИСТЕМЫ"
echo "=================================================="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

# Проверка зависимостей
echo "🔍 Проверка зависимостей..."
python3 -c "
import sys
required_modules = ['yaml', 'pandas', 'numpy', 'lightgbm', 'sklearn']
missing = []
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        missing.append(module)

if missing:
    print(f'❌ Отсутствуют модули: {missing}')
    print('Установите: pip install -r requirements.txt')
    sys.exit(1)
else:
    print('✅ Все зависимости установлены')
"

if [ $? -ne 0 ]; then
    exit 1
fi

# Проверка конфигурации
echo "🔍 Проверка конфигурации..."
if [ ! -f "config/settings.yaml" ]; then
    echo "❌ config/settings.yaml не найден"
    exit 1
fi

if [ ! -f "config/symbols.yaml" ]; then
    echo "❌ config/symbols.yaml не найден"
    exit 1
fi

if [ ! -f "config/models_individual_optimized.yaml" ]; then
    echo "❌ config/models_individual_optimized.yaml не найден"
    exit 1
fi

echo "✅ Конфигурация найдена"

# Проверка ML моделей
echo "🔍 Проверка ML моделей..."
if [ ! -d "forecast/models" ]; then
    echo "❌ Директория forecast/models не найдена"
    exit 1
fi

model_count=$(ls forecast/models/*.joblib 2>/dev/null | wc -l)
if [ $model_count -lt 20 ]; then
    echo "⚠️  Мало ML моделей: $model_count (ожидается >= 20)"
    echo "Запустите обучение: make train-individual"
fi

echo "✅ ML модели проверены"

# Проверка API ключей
echo "🔍 Проверка API ключей..."
if [ -z "$BINANCE_API_KEY" ] || [ -z "$BINANCE_API_SECRET" ]; then
    echo "⚠️  API ключи Binance не установлены"
    echo "   Система будет работать в тестовом режиме"
    echo "   Для лайва установите:"
    echo "   export BINANCE_API_KEY='your_key'"
    echo "   export BINANCE_API_SECRET='your_secret'"
else
    echo "✅ API ключи найдены"
fi

# Финальная проверка системы
echo "🔍 Финальная проверка системы..."
python3 test_system_integration.py
if [ $? -ne 0 ]; then
    echo "❌ Системные тесты не пройдены"
    exit 1
fi

echo ""
echo "🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!"
echo "🚀 Запуск торговой системы..."
echo ""
echo "🛑 Для остановки нажмите Ctrl+C"
echo ""

# Запуск системы
python3 run_trading_system.py
