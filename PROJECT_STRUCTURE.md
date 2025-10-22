# 📁 Структура проекта Orchestrator-Alpha v1.0

## 🎯 Корень проекта

```
AI-Orchestrator Lite/
├── README.md                    # Основная документация
├── Main_Document.txt           # Полная спецификация системы
├── requirements.txt            # Зависимости Python
├── .gitignore                  # Исключения для Git
├── env.example                # Пример переменных окружения
├── Makefile                   # Команды сборки
└── pyproject.toml             # Конфигурация проекта
```

## 📂 Основные папки

### **`orchestrator/`** - Основной код системы
```
orchestrator/
├── app.py                     # Точка входа приложения
├── wiring.py                  # DI контейнер
├── api/                       # REST API
│   ├── server.py             # FastAPI сервер
│   ├── healthcheck.py        # Health check endpoints
│   └── control.py             # Управление системой
├── auction/                   # Аукцион сигналов
│   ├── scorer.py             # Оценка кандидатов
│   ├── selector.py           # Выбор лучшего
│   └── ml_scorer.py          # ML интеграция
├── data/                      # Ингест данных
│   ├── ingest.py             # Загрузка OHLCV
│   ├── features.py           # Фичи для ML
│   ├── models.py             # Модели данных
│   └── cache.py              # Кэширование
├── engine/                    # Движок системы
│   ├── pipeline.py           # Основной пайплайн
│   └── feature_cache.py      # Кэш фичей
├── exec/                      # Исполнение ордеров
│   ├── broker.py             # Брокер интерфейс
│   ├── binance_rest.py       # Binance REST API
│   ├── dummy_broker.py       # Тестовый брокер
│   ├── entry.py              # Вход в позицию
│   ├── exits.py              # Выход из позиции
│   ├── planner.py            # Планировщик ордеров
│   ├── sl_manager.py         # Управление SL
│   ├── order_tracker.py      # Отслеживание ордеров
│   └── slip_impact.py        # Расчет проскальзывания
├── forecast/                  # ML прогнозы
│   ├── base.py               # Базовые классы
│   ├── lgbm_forecaster.py    # LightGBM предсказатель
│   ├── no_ml.py              # NoML режим
│   ├── registry.py           # Реестр моделей
│   ├── labeling.py           # Разметка данных
│   ├── calibrators.py        # Калибраторы вероятностей
│   └── features_builder.py  # Построение фичей
├── guards/                    # Защитные фильтры
│   ├── common.py             # Общие guards
│   ├── conversions.py        # Конверсии сигналов
│   └── realtime_recheck.py   # Real-time проверки
├── risk/                      # Управление рисками
│   ├── limits.py             # Лимиты позиций
│   ├── sizing.py             # Размер позиций
│   └── filters.py            # Риск-фильтры
├── signals/                   # Аналитики сигналов
│   ├── base.py               # Базовые классы
│   ├── breakout.py           # Breakout аналитик
│   ├── pullback_mr.py        # Pullback/MR аналитик
│   ├── trend.py              # Trend аналитик
│   ├── bollinger_play.py     # Bollinger Play аналитик
│   └── helpers.py            # Вспомогательные функции
├── state/                     # Состояние системы
│   ├── store.py              # Хранилище состояния
│   └── recon.py              # Восстановление состояния
├── telemetry/                 # Логирование и метрики
│   ├── logger.py             # Логирование
│   ├── audit.py              # Аудит действий
│   ├── metrics.py            # Метрики производительности
│   ├── reports.py            # Генерация отчетов
│   ├── aggregates.py         # Агрегация данных
│   └── storage.py            # Хранение данных
├── utils/                     # Утилиты
│   ├── mathx.py              # Математические функции
│   ├── timebars.py           # Работа с временными рядами
│   ├── types.py              # Типы данных
│   └── env.py                # Переменные окружения
└── features/                  # Фичи для ML
    └── builder.py            # Построение фичей
```

### **`config/`** - Конфигурация системы
```
config/
├── settings.yaml             # Основные настройки
├── symbols.yaml              # Символы и параметры
├── risk.yaml                 # Управление рисками
├── ladders.yaml              # TP/SL лесенка
├── guards.yaml               # Настройки guards
├── features.yaml             # Настройки фичей
├── reports.yaml              # Настройки отчетов
├── ml_forecast.yaml          # ML конфигурация
└── loader.py                 # Загрузчик конфигурации
```

### **`scripts/`** - Скрипты и утилиты
```
scripts/
├── README.md                 # Документация скриптов
├── auto_train.sh             # Автоматическое обучение
├── train_forecasters.py      # Обучение ML моделей
├── calibrate_forecasters.py  # Калибровка вероятностей
├── export_daily_report.py   # Экспорт отчетов
├── backfill_ohlcv.py         # Загрузка исторических данных
└── nightly_maintenance.sh    # Ночное обслуживание
```

### **`tests/`** - Тесты
```
tests/
├── unit/                     # Юнит тесты
│   ├── test_math_and_indicators.py
│   ├── test_planner.py
│   └── test_recheck_guard.py
├── integration/              # Интеграционные тесты
│   ├── test_e2e_dummy.py
│   └── test_scoring.py
└── fixtures/                 # Тестовые данные
    └── __init__.py
```

### **`docs/`** - Документация
```
docs/
├── Main_Document.md          # Основная документация
├── CONFIGURATION_COMPLETE.md # Руководство по конфигурации
├── DETAILED_VERIFICATION_REPORT.md # Детальная верификация
├── FINAL_INTEGRATION_GUIDE.md # Интеграция ML компонентов
├── INTEGRATION_GUIDE.md      # Руководство по интеграции
├── ML_INTEGRATION_COMPLETE.md # ML интеграция
├── PART_4_INTEGRATION_GUIDE.md # Интеграция Part 4
└── SCRIPTS_INTEGRATION_GUIDE.md # Интеграция скриптов
```

### **`examples/`** - Примеры использования
```
examples/
├── enhanced_lgbm_forecaster_example.py
├── enhanced_pipeline_example.py
├── enhanced_pipeline_integration.py
├── enhanced_scorer_example.py
├── integration_examples.py
├── test_binance_connection.py
├── test_ml_integration.py
└── test_part4_integration.py
```

## 🎯 Ключевые файлы

### **В корне:**
- **`README.md`** - Основная документация проекта
- **`Main_Document.txt`** - Полная спецификация системы
- **`requirements.txt`** - Зависимости Python
- **`.gitignore`** - Исключения для Git

### **Конфигурация:**
- **`config/settings.yaml`** - Основные настройки системы
- **`config/symbols.yaml`** - Активные символы (10 пар)
- **`config/risk.yaml`** - Управление рисками
- **`config/ladders.yaml`** - TP/SL лесенка

### **Основной код:**
- **`orchestrator/app.py`** - Точка входа приложения
- **`orchestrator/engine/pipeline.py`** - Основной пайплайн
- **`orchestrator/auction/scorer.py`** - Оценка сигналов
- **`orchestrator/forecast/lgbm_forecaster.py`** - ML предсказатель

## 🚀 Запуск системы

### **1. Установка:**
```bash
pip install -r requirements.txt
```

### **2. Конфигурация:**
```bash
cp env.example .env
# Отредактируйте .env с API ключами
```

### **3. Обучение ML:**
```bash
./scripts/auto_train.sh
```

### **4. Запуск:**
```bash
python -m orchestrator.app
```

## 📊 Структура данных

### **Входные данные:**
- **OHLCV** - 1h и 15m таймфреймы
- **BTC контекст** - для фильтрации
- **ML модели** - обученные предсказатели

### **Выходные данные:**
- **Telemetry** - логи и метрики
- **Reports** - дневные и недельные отчеты
- **Trades** - история сделок

## 🎉 Заключение

Проект организован по принципу **чистой архитектуры** с четким разделением ответственности:

- **`orchestrator/`** - основная бизнес-логика
- **`config/`** - конфигурация системы
- **`scripts/`** - утилиты и скрипты
- **`tests/`** - тестирование
- **`docs/`** - документация
- **`examples/`** - примеры использования

**Система готова к продакшн использованию!** 🚀
