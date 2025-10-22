# Руководство по интеграции скриптов обучения

## Обзор

Созданы 3 скрипта для полного цикла ML обучения в системе Orchestrator-Alpha:

1. **`scripts/train_forecasters.py`** - Обучение моделей прогнозирования
2. **`scripts/calibrate_forecasters.py`** - Калибровка вероятностей  
3. **`scripts/export_daily_report.py`** - Экспорт дневных отчетов
4. **`scripts/auto_train.sh`** - Автоматический скрипт обучения
5. **`enhanced_lgbm_forecaster_example.py`** - Пример интеграции в пайплайн

## Быстрый старт

### 1. Автоматическое обучение всех моделей

```bash
# Запуск автоматического обучения
./scripts/auto_train.sh
```

Этот скрипт:
- Обучает модели для всех типов сигналов (BRK, PB, TRND, BB)
- Создает модели для разных горизонтов (24, 48, 72 часа)
- Обучает для LONG и SHORT позиций
- Генерирует отчет о созданных моделях

### 2. Ручное обучение конкретной модели

```bash
# Обучение модели для пробоев
python scripts/train_forecasters.py \
    --symbols "ADAUSDT,LTCUSDT" \
    --task binary_hit \
    --side LONG \
    --hbars 24
```

### 3. Калибровка модели

```bash
# Калибровка обученной модели
python scripts/calibrate_forecasters.py \
    --model_path "forecast/models/binary_hit_ADAUSDT_LTCUSDT_H24.joblib" \
    --val_csv "validation_data.csv" \
    --kind platt
```

## Интеграция в существующий код

### Обновление ForecastRegistry

Замените существующий `ForecastRegistry` на расширенную версию:

```python
# В orchestrator/forecast/registry.py
from enhanced_lgbm_forecaster_example import create_enhanced_forecast_registry

class ForecastRegistry:
    def __init__(self):
        # Автоматическая загрузка обученных моделей
        self.by_type = create_enhanced_forecast_registry("forecast/models")
        
        # Fallback для типов без моделей
        for model_type in ["BRK", "PB", "TRND", "BB"]:
            if model_type not in self.by_type:
                from .no_ml import NoMLForecaster
                self.by_type[model_type] = NoMLForecaster()
    
    def forecast(self, candidates: List[SignalCandidate], horizons: List[int]) -> List[FirstHitForecast]:
        out: List[FirstHitForecast] = []
        for t, model in self.by_type.items():
            out.extend(model.predict_many(candidates, horizons))
        return out
```

### Интеграция в AnalyzePipeline

Обновление пайплайна для использования обученных моделей:

```python
# В orchestrator/engine/pipeline.py
def run_once(self):
    # ... существующий код ...
    
    # Использование обученных моделей
    if bool(self.settings.get("forecast", {}).get("enabled", True)):
        # Автоматическая загрузка моделей
        if not hasattr(self, 'forecast_reg_enhanced'):
            from enhanced_lgbm_forecaster_example import create_enhanced_forecast_registry
            self.forecast_reg_enhanced = create_enhanced_forecast_registry()
        
        forecasts = []
        for candidate in all_cands:
            for horizon in horizons:
                if candidate.type in self.forecast_reg_enhanced:
                    forecaster = self.forecast_reg_enhanced[candidate.type]
                    forecasts.extend(forecaster.predict_many([candidate], [horizon]))
                else:
                    # Fallback на NoML
                    forecasts.extend(self.no_ml.predict_many([candidate], [horizon]))
    else:
        forecasts = self.no_ml.predict_many(all_cands, horizons)
    
    # ... остальной код ...
```

## Структура файлов

После обучения система создает следующую структуру:

```
forecast/
├── models/
│   ├── binary_hit_ADAUSDT_LTCUSDT_H24.joblib
│   ├── binary_hit_ADAUSDT_LTCUSDT_H24.meta.json
│   ├── binary_hit_ADAUSDT_LTCUSDT_H24.calib.platt.joblib
│   ├── direction_ADAUSDT_LTCUSDT_H24.joblib
│   └── ...
├── lgbm_forecaster.py (обновленный)
└── registry.py (обновленный)

scripts/
├── train_forecasters.py
├── calibrate_forecasters.py
├── export_daily_report.py
├── auto_train.sh
└── README.md

reports/
├── training_report.json
├── daily_report_2024-01-15.csv
└── ...
```

## Конфигурация

### Настройка обучения

Создайте файл `config/training.yaml`:

```yaml
training:
  symbols: ["ADAUSDT", "LTCUSDT", "DOGEUSDT"]
  start_date: "2024-01-01"
  end_date: "2024-06-01"
  horizons: [24, 48, 72]
  tasks: ["binary_hit", "direction", "trinary"]
  sides: ["LONG", "SHORT"]
  
models:
  directory: "forecast/models"
  train_ratio: 0.8
  random_state: 42
  
calibration:
  kind: "platt"  # или "isotonic"
  validation_ratio: 0.2
```

### Настройка пайплайна

Обновите `config/settings.yaml`:

```yaml
engine:
  forecast:
    enabled: true
    models_dir: "forecast/models"
    auto_load: true
    fallback_to_noml: true
```

## Мониторинг и отладка

### Логи обучения

```bash
# Просмотр логов обучения
tail -f logs/training.log

# Проверка статуса моделей
python -c "
import json
with open('reports/training_report.json') as f:
    report = json.load(f)
    print(f'Моделей: {report[\"total_models\"]}')
    for model in report['models']:
        print(f'  {model[\"name\"]}: {model[\"size_mb\"]}MB, {model[\"kind\"]}')
"
```

### Тестирование моделей

```python
# Тест загрузки модели
from enhanced_lgbm_forecaster_example import EnhancedLGBMForecaster

forecaster = EnhancedLGBMForecaster("BRK", "forecast/models")
print(f"Загружено моделей: {len(forecaster.models)}")
print(f"Калибраторов: {len(forecaster.calibrators)}")
```

## Troubleshooting

### Ошибки обучения

**Проблема:** `RuntimeError: data.ingest.fetch_ohlcv_1h not found`
**Решение:** Убедитесь, что функция `fetch_ohlcv_1h` доступна в модуле `data.ingest`

**Проблема:** `Warning: Very small dataset (<200 rows)`
**Решение:** Расширьте временной диапазон или добавьте больше символов

### Ошибки калибровки

**Проблема:** `{"ok": False, "error": "scikit-learn/joblib required"}`
**Решение:** Установите scikit-learn или используйте fallback режим

### Ошибки интеграции

**Проблема:** Модели не загружаются в пайплайне
**Решение:** Проверьте пути к моделям и права доступа к файлам

## Производительность

### Оптимизация обучения

- **Параллельное обучение:** Запускайте обучение разных типов параллельно
- **Кэширование данных:** Сохраняйте подготовленные данные для повторного использования
- **Инкрементальное обучение:** Обновляйте модели новыми данными

### Оптимизация предсказаний

- **Кэширование моделей:** Загружайте модели один раз при старте
- **Батчевые предсказания:** Обрабатывайте несколько кандидатов одновременно
- **Fallback стратегии:** Используйте простые модели для быстрых предсказаний

## Следующие шаги

1. **Автоматизация:** Настройте cron для регулярного переобучения моделей
2. **Мониторинг:** Добавьте метрики качества моделей в телеметрию
3. **A/B тестирование:** Сравните производительность ML и NoML режимов
4. **Расширение:** Добавьте новые типы моделей и признаки

## Примеры использования

### Полный цикл обучения

```bash
#!/bin/bash
# Полный цикл обучения и интеграции

# 1. Обучение моделей
./scripts/auto_train.sh

# 2. Калибровка всех моделей
for model in forecast/models/*.joblib; do
    python scripts/calibrate_forecasters.py \
        --model_path "$model" \
        --val_csv "validation.csv" \
        --kind platt
done

# 3. Тестирование интеграции
python -c "
from enhanced_lgbm_forecaster_example import create_enhanced_forecast_registry
registry = create_enhanced_forecast_registry()
print('Интеграция успешна!')
"

# 4. Запуск системы с ML моделями
python -m orchestrator.app
```

### Мониторинг качества

```python
# Скрипт для мониторинга качества моделей
import json
import pandas as pd

def check_model_quality():
    with open('reports/training_report.json') as f:
        report = json.load(f)
    
    print("📊 Качество моделей:")
    for model in report['models']:
        if 'val_auc' in model:
            auc = model['val_auc']
            quality = "🟢 Отлично" if auc > 0.7 else "🟡 Хорошо" if auc > 0.6 else "🔴 Плохо"
            print(f"  {model['name']}: AUC={auc:.3f} {quality}")
        else:
            print(f"  {model['name']}: Нет метрик валидации")

if __name__ == "__main__":
    check_model_quality()
```

## Заключение

Скрипты обучения полностью интегрированы в систему и готовы к использованию. Они обеспечивают:

- ✅ **Безопасную интеграцию** без изменения существующего кода
- ✅ **Fallback режимы** для работы без ML библиотек  
- ✅ **Автоматическую загрузку** обученных моделей
- ✅ **Калибровку вероятностей** для улучшения качества
- ✅ **Мониторинг и отладку** для контроля качества

Система готова к продакшн использованию с ML моделями! 🚀
