.PHONY: setup run backfill train calibrate report tests clean

setup:        ## установить зависимости
	pip install -e .

run:          ## старт live-движка
	python -m orchestrator.app

backfill:     ## подкачка истории
	python scripts/backfill_ohlcv.py

train:        ## обучение моделей
	python scripts/train_forecasters.py

calibrate:    ## калибровка
	python scripts/calibrate_forecasters.py

report:       ## сгенерить дневной отчёт
	python scripts/export_daily_report.py

tests:        ## запустить тесты
	pytest tests/ -v

clean:        ## очистить временные файлы
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
