# =========================
# ML TRAIN & CALIB PIPELINE (H12 + H24 ENSEMBLE)
# =========================
SHELL := /bin/bash
PY := python

# === Символы ===
A_SYMBOLS := ADAUSDT,HBARUSDT,LTCUSDT
B_SYMBOLS := PNUTUSDT,WIFUSDT,ENAUSDT,DOGEUSDT,ARBUSDT,SUIUSDT,SEIUSDT

# === Общие настройки ===
TASK := binary_hit
ENTRY := open_t
FLAGS := --both_sides --symbol_balance --corr_dropout 0.15
MODELS_DIR := forecast/models

# === Горизонты ===
H12 := 12
H24 := 24

# === Имена моделей ===
A_MODEL_H12 := $(MODELS_DIR)/$(TASK)_ADAUSDT_and_2_more_H$(H12).joblib
B_MODEL_H12 := $(MODELS_DIR)/$(TASK)_PNUTUSDT_and_6_more_H$(H12).joblib
A_MODEL_H24 := $(MODELS_DIR)/$(TASK)_ADAUSDT_and_2_more_H$(H24).joblib
B_MODEL_H24 := $(MODELS_DIR)/$(TASK)_PNUTUSDT_and_6_more_H$(H24).joblib

.DEFAULT_GOAL := all

# ===== Targets =====

.PHONY: all
all: train_A_H12 train_B_H12 train_A_H24 train_B_H24 calibrate_A_H12 calibrate_B_H12 calibrate_A_H24 calibrate_B_H24 models_yaml done

# ====== TRAIN TARGETS ======

.PHONY: train_A_H12
train_A_H12:
	$(PY) scripts/train_forecasters.py --symbols "$(A_SYMBOLS)" --task $(TASK) --hbars $(H12) --entry_mode $(ENTRY) $(FLAGS) --models_dir $(MODELS_DIR)

.PHONY: train_B_H12
train_B_H12:
	$(PY) scripts/train_forecasters.py --symbols "$(B_SYMBOLS)" --task $(TASK) --hbars $(H12) --entry_mode $(ENTRY) $(FLAGS) --models_dir $(MODELS_DIR)

.PHONY: train_A_H24
train_A_H24:
	$(PY) scripts/train_forecasters.py --symbols "$(A_SYMBOLS)" --task $(TASK) --hbars $(H24) --entry_mode $(ENTRY) $(FLAGS) --models_dir $(MODELS_DIR)

.PHONY: train_B_H24
train_B_H24:
	$(PY) scripts/train_forecasters.py --symbols "$(B_SYMBOLS)" --task $(TASK) --hbars $(H24) --entry_mode $(ENTRY) $(FLAGS) --models_dir $(MODELS_DIR)

# ====== CALIB TARGETS ======

.PHONY: calibrate_A_H12
calibrate_A_H12:
	$(PY) scripts/calibrate_forecasters.py --model_path $(A_MODEL_H12) --val_csv data/val/$(TASK)_H$(H12)_VAL.csv --kind isotonic

.PHONY: calibrate_B_H12
calibrate_B_H12:
	$(PY) scripts/calibrate_forecasters.py --model_path $(B_MODEL_H12) --val_csv data/val/$(TASK)_H$(H12)_VAL.csv --kind isotonic

.PHONY: calibrate_A_H24
calibrate_A_H24:
	$(PY) scripts/calibrate_forecasters.py --model_path $(A_MODEL_H24) --val_csv data/val/$(TASK)_H$(H24)_VAL.csv --kind isotonic

.PHONY: calibrate_B_H24
calibrate_B_H24:
	$(PY) scripts/calibrate_forecasters.py --model_path $(B_MODEL_H24) --val_csv data/val/$(TASK)_H$(H24)_VAL.csv --kind isotonic

# ====== Генерация models.yaml с ансамблем H12+H24 ======

.PHONY: models_yaml
models_yaml:
	$(PY) scripts/gen_models_yaml.py --a12 $(A_MODEL_H12) --b12 $(B_MODEL_H12) --a24 $(A_MODEL_H24) --b24 $(B_MODEL_H24) --out config/models.yaml

# ====== Per-Signal Models ======

SYMS := ADAUSDT HBARUSDT LTCUSDT PNUTUSDT WIFUSDT ENAUSDT DOGEUSDT ARBUSDT SUIUSDT SEIUSDT

.PHONY: train-per-signal
train-per-signal:
	@echo "Training per-signal models..."
	$(PY) scripts/train_forecasters_per_signal.py --symbols $(SYMS)

.PHONY: calibrate-per-signal
calibrate-per-signal:
	@echo "Calibrating per-signal models..."
	$(PY) scripts/calibrate_per_signal.py --symbols $(SYMS)

.PHONY: gen-yaml-per-signal
gen-yaml-per-signal:
	@echo "Generating per-signal YAML..."
	$(PY) scripts/gen_models_yaml_per_signal.py --symbols $(SYMS)

# Генерация меток сигналов
.PHONY: build-signal-marks
build-signal-marks:
	@echo "Building signal marks..."
	$(PY) scripts/build_signal_marks.py --symbols $(SYMS)

# Полный пайплайн per-signal (обновлён): сначала марки, затем обучение и калибровка
.PHONY: per-signal-all
per-signal-all: build-signal-marks train-per-signal calibrate-per-signal gen-yaml-per-signal
	@echo "Per-signal models trained, calibrated and YAML generated."

.PHONY: done
done:
	@echo "✅ Ensemble pipeline finished. A/B models for H12 & H24 are trained, calibrated, and configured."