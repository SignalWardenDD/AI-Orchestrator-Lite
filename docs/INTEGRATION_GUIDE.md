# Руководство по интеграции новых модулей

## Обзор

Добавлены 4 новых фундаментальных модуля, которые можно безопасно интегрировать в существующую систему без изменения работающего кода:

1. **`utils/mathx.py`** - Математические функции для анализа данных
2. **`risk/filters.py`** - Дополнительные риск-фильтры
3. **`forecast/labeling.py`** - Разметка данных для ML обучения
4. **`forecast/calibrators.py`** - Калибраторы вероятностей

## Безопасная интеграция

### 1. Математические функции (`utils/mathx.py`)

```python
from orchestrator.utils.mathx import natr, rolling_corr, sigmoid, zscore

# Использование в существующем коде
def enhanced_feature_calculation(ohlc_data):
    # NATR для волатильности
    natr_series = natr(ohlc_data['high'], ohlc_data['low'], ohlc_data['close'])
    
    # Z-score для нормализации
    vol_zscore = zscore(natr_series, window=20)
    
    # Сигмоид для нормализации в 0-1
    normalized_vol = sigmoid(vol_zscore)
    
    return normalized_vol
```

### 2. Риск-фильтры (`risk/filters.py`)

```python
from orchestrator.risk.filters import CalmMarketGuard, SpikeGuard, CorrBlocker

# Создание фильтров
calm_guard = CalmMarketGuard(threshold_pct=0.8)
spike_guard = SpikeGuard(window=24, spike_mult=4.0)
corr_blocker = CorrBlocker(window=48, max_corr=0.95)

# Использование в пайплайне
def enhanced_candidate_filtering(candidate, ohlc_data, btc_data):
    # Проверка спокойного рынка
    allowed, reason, meta = calm_guard.check(ohlc_data)
    if not allowed:
        return False, reason
    
    # Проверка на спайки
    allowed, reason, meta = spike_guard.check(ohlc_data['close'])
    if not allowed:
        return False, reason
    
    # Проверка корреляции с BTC
    allowed, reason, meta = corr_blocker.check(ohlc_data['close'], btc_data['close'])
    if not allowed:
        return False, reason
    
    return True, "PASSED"
```

### 3. Разметка данных (`forecast/labeling.py`)

```python
from orchestrator.forecast.labeling import build_labels, HorizonSpec

# Создание спецификации горизонта
horizon_spec = HorizonSpec(
    horizon_bars=24,  # 24 часа
    tp_mult_atr=2.0,  # TP на 2 ATR
    sl_mult_atr=2.0   # SL на 2 ATR
)

# Создание лейблов для разных задач
labels_binary = build_labels(
    ohlc_data, atr_series, horizon_spec, 
    task="binary_hit", side="LONG"
)

labels_direction = build_labels(
    ohlc_data, atr_series, horizon_spec,
    task="direction", side="LONG"
)
```

### 4. Калибраторы (`forecast/calibrators.py`)

```python
from orchestrator.forecast.calibrators import Calibrator, calibration_report

# Создание калибратора
calibrator = Calibrator(kind="platt")

# Обучение калибратора
calibrator.fit(raw_scores, true_labels)

# Получение калиброванных вероятностей
calibrated_probs = calibrator.predict_proba(raw_scores)

# Отчет о калибровке
report = calibration_report(raw_scores, true_labels, kind="platt")
```

## Примеры интеграции

### Расширенный пайплайн

См. файл `enhanced_pipeline_example.py` для полного примера интеграции в `AnalyzePipeline`.

### Дополнительные примеры

См. файл `integration_examples.py` для различных сценариев использования.

## Совместимость

- ✅ **Полная совместимость** с существующим кодом
- ✅ **Безопасная интеграция** - не требует изменений в работающих частях
- ✅ **Постепенное внедрение** - можно добавлять модули по одному
- ✅ **Fallback режим** - работает без ML зависимостей

## Следующие шаги

1. **Часть 2** - Тренировочные скрипты (`scripts/train_forecasters.py`, `scripts/calibrate_forecasters.py`, `scripts/export_daily_report.py`)
2. **Интеграция в LGBMForecaster** - подключение калибраторов к ML моделям
3. **Расширение пайплайнов** - добавление новых фильтров в основные циклы

## Тестирование

Все модули протестированы на совместимость и не содержат ошибок линтера. Можно безопасно интегрировать в продакшн систему.
