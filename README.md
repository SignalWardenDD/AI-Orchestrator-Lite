# 🎯 Orchestrator-Alpha v1.0

**Автоматизированная торговая система для Binance USDT-M Futures**

## 📋 Обзор

Orchestrator-Alpha v1.0 — это интеллектуальная торговая система, работающая 24/7 на Mac Air M2, которая:

- **Предсказывает исходы** в ближайшие часы с помощью ML моделей
- **Не лезет в опасные входы** благодаря системе фильтров и guards
- **Работает тихо** без мешающих основной работе процессов
- **Даёт активность** через 4 независимых аналитика сигналов

## 🏗️ Архитектура

### **Слои системы:**

1. **Data Ingest** - OHLCV данные, базовые индикаторы, BTC-контекст
2. **4 Аналитика** - Breakout, Pullback/MR, Trend-Follower, Bollinger-Play
3. **Per-Type Forecast** - ML модели для предсказания исходов
4. **Guards** - Защита от опасных входов
5. **Signal Auction** - Выбор лучшего кандидата по денежной метрике
6. **Real-Time Re-Check** - Финальная валидация перед входом
7. **Execution** - PostOnly LIMIT с market fallback
8. **Risk & Exits** - Ступенчатые TP, денежный BE
9. **Telemetry** - Аудит, отчеты, метрики

## 🚀 Быстрый старт

### **1. Установка зависимостей:**
```bash
pip install -r requirements.txt
```

### **2. Настройка конфигурации:**
```bash
cp env.example .env
# Отредактируйте .env с вашими API ключами Binance
```

### **3. Обучение ML моделей:**
```bash
./scripts/auto_train.sh
```

### **4. Запуск системы:**
```bash
python -m orchestrator.app
```

## 📊 Активный портфель

### **A-группа (умеренные тренды):**
- **ADAUSDT** - Cardano
- **HBARUSDT** - Hedera  
- **LTCUSDT** - Litecoin

### **B-группа (спайковые активы):**
- **PNUTUSDT** - Peanut
- **WIFUSDT** - dogwifhat
- **ENAUSDT** - Ethena
- **DOGEUSDT** - Dogecoin
- **ARBUSDT** - Arbitrum
- **SUIUSDT** - Sui
- **SEIUSDT** - Sei

## ⚙️ Ключевые параметры

- **Позиция**: 15 USDT, плечо 5×
- **Таймфреймы**: 1h (базовый), 15m (микро)
- **Циклы**: анализ каждые 2 мин, проверка ордеров каждые 15 сек
- **TP лесенка**: 20% @ +0.6×ATR, 25% @ +1.2×ATR, 25% @ +2.0×ATR, 30% @ +3.2×ATR
- **SL множители**: BRK 1.3×ATR, PB 2.0×ATR, Trend 1.8×ATR, BB 1.6×ATR

## 📈 Ожидаемые результаты

### **KPI старта:**
- **Weekly PF**: ≥ 1.10-1.15
- **Win Rate**: 40-55%
- **TP2+ сделки**: ≥ 35%
- **Fill-rate лимитов**: ≥ 65%
- **Средний fallback-slippage**: ≤ 0.10-0.12%

## 📁 Структура проекта

```
orchestrator/           # Основной код системы
├── api/               # REST API
├── auction/           # Аукцион сигналов
├── data/              # Ингест данных
├── engine/            # Движок системы
├── exec/              # Исполнение ордеров
├── forecast/          # ML прогнозы
├── guards/            # Защитные фильтры
├── risk/              # Управление рисками
├── signals/           # Аналитики сигналов
├── state/             # Состояние системы
├── telemetry/         # Логирование и метрики
└── utils/             # Утилиты

config/                # Конфигурация
├── settings.yaml      # Основные настройки
├── symbols.yaml       # Символы и параметры
├── risk.yaml          # Управление рисками
└── ladders.yaml       # TP/SL лесенка

scripts/               # Скрипты
├── train_forecasters.py    # Обучение ML моделей
├── calibrate_forecasters.py # Калибровка вероятностей
└── export_daily_report.py  # Экспорт отчетов

tests/                 # Тесты
├── unit/              # Юнит тесты
└── integration/       # Интеграционные тесты
```

## 🔧 Конфигурация

### **Основные файлы:**
- `config/settings.yaml` - общие настройки системы
- `config/symbols.yaml` - активные символы и параметры
- `config/risk.yaml` - управление рисками
- `config/ladders.yaml` - TP/SL лесенка

### **ML настройки:**
- `config/ml.yaml` - параметры ML моделей
- `forecast/models/` - обученные модели
- `scripts/train_forecasters.py` - обучение моделей

## 📊 Мониторинг

### **Логи:**
- `telemetry/audit.log` - аудит всех действий
- `telemetry/trades.csv` - история сделок
- `telemetry/orders.csv` - история ордеров

### **Отчеты:**
- `reports/daily_report_YYYY-MM-DD.csv` - дневные отчеты
- `reports/weekly_report_YYYY-MM-DD.csv` - недельные отчеты

## 🛡️ Безопасность

- **PostOnly LIMIT** ордера с TTL 8-12 сек
- **Market fallback** с ограничением slippage
- **Reduce-only** для всех TP/SL
- **Дневной лимит убытка**: -7.5 USDT
- **Недельный лимит**: 3 отрицательных дня подряд

## 📚 Документация

- `Main_Document.txt` - Полная спецификация системы
- `CONFIGURATION_COMPLETE.md` - Руководство по конфигурации
- `FINAL_INTEGRATION_GUIDE.md` - Интеграция ML компонентов
- `scripts/README.md` - Документация скриптов

## 🤝 Поддержка

Система спроектирована для работы в продакшн с минимальным вмешательством. Все компоненты имеют fallback механизмы и graceful degradation.

---

**Orchestrator-Alpha v1.0** - Интеллектуальная торговая система нового поколения 🚀