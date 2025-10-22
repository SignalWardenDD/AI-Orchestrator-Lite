# Скрипты для обучения и калибровки моделей

## Обзор

Три скрипта для полного цикла ML обучения в системе Orchestrator-Alpha:

1. **`train_forecasters.py`** - Обучение моделей прогнозирования
2. **`calibrate_forecasters.py`** - Калибровка вероятностей
3. **`export_daily_report.py`** - Экспорт дневных отчетов

## Безопасность

- ✅ **Работают без ML зависимостей** - есть fallback режимы
- ✅ **Совместимы с существующим кодом** - не требуют изменений
- ✅ **Graceful degradation** - при отсутствии библиотек переходят на простые методы

## Использование

### 1. Обучение моделей (`train_forecasters.py`)

```bash
# Базовое обучение
python scripts/train_forecasters.py --symbols "ADAUSDT,LTCUSDT" --task binary_hit --side LONG

# Расширенные параметры
python scripts/train_forecasters.py \
    --symbols "ADAUSDT,LTCUSDT,DOGEUSDT" \
    --start "2024-01-01" \
    --end "2024-06-01" \
    --task binary_hit \
    --side LONG \
    --hbars 24 \
    --tp_atr 2.0 \
    --sl_atr 2.0 \
    --models_dir "forecast/models" \
    --train_ratio 0.8
```

**Параметры:**
- `--symbols` - Символы для обучения (обязательно)
- `--start/--end` - Временной диапазон (опционально)
- `--task` - Тип задачи: `binary_hit`, `direction`, `trinary`, `regression`
- `--side` - Направление: `LONG` или `SHORT`
- `--hbars` - Горизонт в барах (по умолчанию 24)
- `--tp_atr/sl_atr` - Множители ATR для TP/SL
- `--models_dir` - Директория для сохранения моделей
- `--train_ratio` - Доля данных для обучения (0.8 = 80%)

**Результат:**
- Модель сохраняется в `forecast/models/`
- Создается `*.meta.json` с метаданными
- Возвращает JSON с результатами обучения

### 2. Калибровка вероятностей (`calibrate_forecasters.py`)

```bash
# Калибровка модели
python scripts/calibrate_forecasters.py \
    --model_path "forecast/models/binary_hit_ADAUSDT_H24.joblib" \
    --val_csv "data/validation.csv" \
    --kind platt \
    --out_dir "forecast/models"
```

**Параметры:**
- `--model_path` - Путь к обученной модели (обязательно)
- `--val_csv` - CSV с валидационными данными (обязательно)
- `--kind` - Тип калибратора: `platt` или `isotonic`
- `--out_dir` - Директория для сохранения калибратора

**Результат:**
- Калибратор сохраняется как `*.calib.{kind}.joblib`
- Возвращает отчет о калибровке (Brier score, ECE)

### 3. Экспорт отчетов (`export_daily_report.py`)

```bash
# Экспорт дневного отчета
python scripts/export_daily_report.py \
    --telemetry_dir "data" \
    --out_dir "reports" \
    --tz "Europe/Kyiv"
```

**Параметры:**
- `--telemetry_dir` - Директория с CSV файлами телеметрии (обязательно)
- `--out_dir` - Директория для сохранения отчетов
- `--tz` - Часовой пояс для группировки по дням

**Результат:**
- Создается `reports/daily_report_YYYY-MM-DD.csv`
- Возвращает JSON с информацией об экспорте

## Форматы данных

### Входные данные для обучения

Скрипт ожидает функцию `fetch_ohlcv_1h(symbol, start, end)` которая возвращает DataFrame с колонками:
- `open`, `high`, `low`, `close` - OHLC данные
- `volume` - объем (опционально)
- Индекс должен быть DatetimeIndex

### Валидационные данные для калибровки

CSV файл должен содержать:
- Колонки с признаками (соответствующие `feature_names` из модели)
- Колонку `y` с бинарными метками (0/1)

### Телеметрия для отчетов

CSV файлы в директории телеметрии:
- `trades.csv` - данные о сделках
- `orders.csv` - данные об ордерах (опционально)

Ожидаемые колонки в `trades.csv`:
- `symbol`, `side` - символ и направление
- `pnl_usdt` - прибыль/убыток в USDT
- `opened_at`/`closed_at` - времена открытия/закрытия
- `timestamp` - общий timestamp (fallback)

## Fallback режимы

### Без LightGBM/Sklearn

Если ML библиотеки недоступны, скрипты используют:
- **Линейные модели** - взвешенная сумма признаков
- **Простая нормализация** - масштабирование в [0,1]
- **Базовые метрики** - корреляции и статистики

### Без данных

Если данные недоступны:
- **Предупреждения** - скрипты предупреждают о малом объеме данных
- **Минимальные требования** - работают с 200+ строками
- **Graceful handling** - обрабатывают ошибки без падения

## Интеграция с существующим кодом

### В ForecastRegistry

```python
# Автоматическая загрузка обученных моделей
from forecast.registry import ForecastRegistry

registry = ForecastRegistry()
# Загружает модели из forecast/models/ если они есть
```

### В пайплайне

```python
# Использование калиброванных вероятностей
from forecast.calibrators import Calibrator

# Загрузка калибратора
calib = Calibrator.load("forecast/models/model.calib.platt.joblib")

# Калибровка сырых предсказаний
calibrated_probs = calib.predict_proba(raw_scores)
```

## Примеры использования

### Полный цикл обучения

```bash
# 1. Обучение модели
python scripts/train_forecasters.py \
    --symbols "ADAUSDT,LTCUSDT" \
    --task binary_hit \
    --side LONG

# 2. Подготовка валидационных данных (создать validation.csv)
# 3. Калибровка
python scripts/calibrate_forecasters.py \
    --model_path "forecast/models/binary_hit_ADAUSDT_LTCUSDT_H24.joblib" \
    --val_csv "validation.csv" \
    --kind platt

# 4. Экспорт отчетов
python scripts/export_daily_report.py \
    --telemetry_dir "data" \
    --out_dir "reports"
```

### Автоматизация

```bash
#!/bin/bash
# Скрипт автоматического обучения

# Обучение для разных типов
for task in binary_hit direction trinary; do
    python scripts/train_forecasters.py \
        --symbols "ADAUSDT,LTCUSDT" \
        --task $task \
        --side LONG
done

# Калибровка всех моделей
for model in forecast/models/*.joblib; do
    python scripts/calibrate_forecasters.py \
        --model_path "$model" \
        --val_csv "validation.csv" \
        --kind platt
done
```

## Troubleshooting

### Ошибки импорта

```
RuntimeError: data.ingest.fetch_ohlcv_1h not found
```
**Решение:** Убедитесь, что функция `fetch_ohlcv_1h` доступна в модуле `data.ingest`

### Мало данных

```
Warning: Very small dataset (<200 rows)
```
**Решение:** Расширьте временной диапазон или добавьте больше символов

### Отсутствие ML библиотек

```
{"ok": False, "error": "scikit-learn/joblib required for calibration"}
```
**Решение:** Установите scikit-learn или используйте fallback режим

## Следующие шаги

После создания скриптов можно переходить к **Части 3** - интеграции в `forecast/lgbm_forecaster.py` для автоматической загрузки обученных моделей в пайплайн.
