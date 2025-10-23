# 🚀 AI-Orchestrator Lite

**Автоматизированная торговая система с ML-прогнозированием**

---

## 📁 Структура проекта

```
AI-Orchestrator Lite/
├── orchestrator/              # Основной код системы
│   ├── api/                   # API эндпоинты
│   ├── auction/               # Аукцион сигналов
│   ├── data/                  # Загрузка данных
│   ├── engine/                # Основной движок
│   ├── exec/                  # Исполнение ордеров
│   ├── forecast/              # ML прогнозирование
│   ├── guards/                # Защитные механизмы
│   ├── risk/                  # Управление рисками
│   ├── signals/               # Провайдеры сигналов
│   ├── state/                 # Состояние системы
│   ├── telemetry/             # Логирование и метрики
│   └── utils/                 # Утилиты
├── config/                    # Конфигурации
│   ├── optimized/             # Оптимизированные настройки
│   └── examples/              # Примеры конфигураций
├── data/                      # Данные
│   ├── raw/                   # Сырые данные
│   ├── processed/             # Обработанные данные
│   ├── cache/                 # Кэш
│   ├── models/                # ML модели
│   └── signals/               # Сигнальные метки
├── docs/                      # Документация
├── scripts/                   # Скрипты
├── tests/                     # Тесты
├── examples/                  # Примеры использования
├── reports/                   # Отчеты
├── logs/                      # Логи
└── README.md                  # Этот файл
```

---

## 🎯 Основные возможности

### 🧠 ML-прогнозирование
- **Per-signal модели** - специализированные для каждого типа сигнала
- **Индивидуальные модели** - для каждой торговой пары
- **Ансамблирование** - комбинирование H12/H24 горизонтов
- **Калибровка вероятностей** - точные прогнозы

### 📊 Сигнальные провайдеры
- **Breakout** - прорывы уровней
- **Pullback/MR** - откаты и возвраты к среднему
- **Trend** - трендовые сигналы
- **Bollinger Play** - игра от границ Боллинджера

### 🛡️ Защитные механизмы
- **Риск-менеджмент** - лимиты позиций и потерь
- **Умная синхронизация** - сверка с биржей
- **Анти-чурнинг** - предотвращение избыточных операций
- **Tier-стратегия** - приоритизация сильных моделей

### ⚡ Исполнение
- **PostOnly ордера** - минимальные комиссии
- **Многоступенчатый TP/SL** - максимизация прибыли
- **Трейлинг SL** - защита от убытков
- **PnL-based выходы** - точное управление рисками

---

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации
```bash
# Копируем пример конфигурации
cp env.example .env

# Редактируем настройки
nano .env
```

### 3. Загрузка данных
```bash
# Загружаем исторические данные
python3 scripts/fetch_binance_futures.py

# Генерируем сигнальные метки
make build-signal-marks
```

### 4. Обучение моделей
```bash
# Обучаем индивидуальные модели
make train-individual

# Калибруем модели
make calibrate-individual

# Генерируем конфигурацию
make gen-yaml-individual
```

### 5. Запуск системы
```bash
# Запускаем оркестратор
python3 orchestrator/app.py

# Или через скрипт
./start_trading.sh
```

---

## 📊 Мониторинг

### Логи
```bash
# Основные логи
tail -f logs/orchestrator.log

# Аудит
tail -f logs/audit.log
```

### API
```bash
# Статус системы
curl http://localhost:8000/health

# Метрики
curl http://localhost:8000/metrics
```

### Отчеты
```bash
# Анализ качества моделей
python3 scripts/analyze_model_quality.py

# Экспорт дневного отчета
python3 scripts/export_daily_report.py
```

---

## 🔧 Конфигурация

### Основные настройки
- `config/settings.yaml` - основные параметры
- `config/risk.yaml` - управление рисками
- `config/symbols.yaml` - торговые пары
- `config/ladders.yaml` - лесенки TP/SL

### Оптимизированные настройки
- `config/optimized/` - оптимизированные конфигурации
- `config/optimized/README_OPTIMIZED.md` - инструкции

---

## 🧪 Тестирование

### Запуск тестов
```bash
# Все тесты
python3 -m pytest tests/

# Конкретный тест
python3 tests/unit/test_math_and_indicators.py

# Комплексное тестирование
python3 scripts/comprehensive_system_test.py
```

### Проверка качества
```bash
# Анализ моделей
python3 scripts/analyze_model_quality.py

# Проверка готовности
python3 scripts/test_per_signal_readiness.py
```

---

## 📈 Производительность

### Ожидаемые результаты
- **Прибыльность:** +8-20% годовых
- **Точность:** 55-60% hit rate
- **Риск:** контролируемый drawdown
- **Стабильность:** 99%+ uptime

### Tier-стратегия
- **Tier 1:** DOGEUSDT, SEIUSDT, LTCUSDT, ARBUSDT (активная торговля)
- **Tier 2:** ADAUSDT, SUIUSDT (ограниченная торговля)
- **Tier 3:** WIFUSDT, HBARUSDT, PNUTUSDT, ENAUSDT (отключены)

---

## 🛠️ Разработка

### Структура кода
- `orchestrator/` - основной код системы
- `scripts/` - утилиты и скрипты
- `tests/` - тесты
- `examples/` - примеры использования

### Добавление новых функций
1. Создайте модуль в `orchestrator/`
2. Добавьте тесты в `tests/`
3. Обновите документацию
4. Запустите тесты

---

## 📞 Поддержка

### Полезные команды
```bash
# Проверка системы
python3 scripts/comprehensive_system_test.py

# Анализ качества
python3 scripts/analyze_model_quality.py

# Очистка кэша
rm -rf data/cache/*

# Перезапуск
pkill -f orchestrator && python3 orchestrator/app.py
```

### Логи и отладка
- Основные логи: `logs/orchestrator.log`
- Аудит: `logs/audit.log`
- Отчеты: `reports/`

---

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей.

---

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

---

**🚀 Удачной торговли!**