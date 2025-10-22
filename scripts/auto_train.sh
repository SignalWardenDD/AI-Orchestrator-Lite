#!/bin/bash
# scripts/auto_train.sh
# Автоматический скрипт для обучения всех моделей

set -e  # Остановка при ошибке

echo "🚀 Начинаем автоматическое обучение моделей..."

# Создаем директории
mkdir -p forecast/models
mkdir -p data/cache
mkdir -p reports

# Параметры обучения
SYMBOLS="ADAUSDT,LTCUSDT,DOGEUSDT"
START_DATE="2024-01-01"
END_DATE="2024-06-01"
MODELS_DIR="forecast/models"

echo "📊 Параметры обучения:"
echo "  Символы: $SYMBOLS"
echo "  Период: $START_DATE - $END_DATE"
echo "  Директория моделей: $MODELS_DIR"

# Функция для обучения модели
train_model() {
    local task=$1
    local side=$2
    local hbars=$3
    local tp_atr=$4
    local sl_atr=$5
    
    echo "🎯 Обучение: $task, $side, H$hbars, TP${tp_atr}ATR, SL${sl_atr}ATR"
    
    python scripts/train_forecasters.py \
        --symbols "$SYMBOLS" \
        --start "$START_DATE" \
        --end "$END_DATE" \
        --task "$task" \
        --side "$side" \
        --hbars "$hbars" \
        --tp_atr "$tp_atr" \
        --sl_atr "$sl_atr" \
        --models_dir "$MODELS_DIR" \
        --train_ratio 0.8
}

# Обучение для разных типов задач
echo "📈 Обучение моделей для LONG позиций..."

# Binary hit модели для разных горизонтов
train_model "binary_hit" "LONG" 24 2.0 2.0
train_model "binary_hit" "LONG" 48 2.0 2.0
train_model "binary_hit" "LONG" 72 2.0 2.0

# Direction модели
train_model "direction" "LONG" 24 2.0 2.0
train_model "direction" "LONG" 48 2.0 2.0

# Trinary модели
train_model "trinary" "LONG" 24 2.0 2.0

# Regression модели
train_model "regression" "LONG" 24 2.0 2.0

echo "📉 Обучение моделей для SHORT позиций..."

# Binary hit модели для SHORT
train_model "binary_hit" "SHORT" 24 2.0 2.0
train_model "binary_hit" "SHORT" 48 2.0 2.0

# Direction модели для SHORT
train_model "direction" "SHORT" 24 2.0 2.0

echo "✅ Обучение завершено!"

# Список созданных моделей
echo "📁 Созданные модели:"
ls -la "$MODELS_DIR"/*.joblib 2>/dev/null || echo "  Модели не найдены"

# Создание отчета
echo "📊 Создание отчета о моделях..."
python -c "
import os, json, glob
from pathlib import Path

models_dir = '$MODELS_DIR'
models = glob.glob(os.path.join(models_dir, '*.joblib'))
meta_files = glob.glob(os.path.join(models_dir, '*.meta.json'))

report = {
    'total_models': len(models),
    'models': [],
    'meta_files': len(meta_files)
}

for model_path in models:
    model_name = os.path.basename(model_path)
    meta_path = model_path.replace('.joblib', '.meta.json')
    
    model_info = {
        'name': model_name,
        'path': model_path,
        'size_mb': round(os.path.getsize(model_path) / 1024 / 1024, 2),
        'has_meta': os.path.exists(meta_path)
    }
    
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            model_info.update({
                'task': meta.get('task', 'unknown'),
                'side': meta.get('side', 'unknown'),
                'horizon_bars': meta.get('horizon_bars', 'unknown'),
                'feature_count': len(meta.get('feature_names', [])),
                'kind': meta.get('kind', 'unknown')
            })
        except Exception as e:
            model_info['meta_error'] = str(e)
    
    report['models'].append(model_info)

# Сохраняем отчет
with open('reports/training_report.json', 'w') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f'📋 Отчет сохранен: reports/training_report.json')
print(f'📊 Всего моделей: {len(models)}')
print(f'📄 Мета-файлов: {len(meta_files)}')
"

echo "🎉 Автоматическое обучение завершено успешно!"
echo "📁 Результаты сохранены в: $MODELS_DIR"
echo "📊 Отчет: reports/training_report.json"
