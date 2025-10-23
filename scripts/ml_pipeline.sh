#!/usr/bin/env bash
set -euo pipefail

TASK="binary_hit"
ENTRY="open_t"
FLAGS="--both_sides --symbol_balance --corr_dropout 0.15"

A_SYMBOLS="ADAUSDT,HBARUSDT,LTCUSDT"
B_SYMBOLS="PNUTUSDT,WIFUSDT,ENAUSDT,DOGEUSDT,ARBUSDT,SUIUSDT,SEIUSDT"

MODELS_DIR="forecast/models"

# H12 models
H12=12
VAL_PARQUET_H12="data/processed/val_H${H12}.parquet"
VAL_CSV_H12="data/val/${TASK}_H${H12}_VAL.csv"
A_MODEL_H12="${MODELS_DIR}/${TASK}_ADAUSDT_and_2_more_H${H12}.joblib"
B_MODEL_H12="${MODELS_DIR}/${TASK}_PNUTUSDT_and_6_more_H${H12}.joblib"

# H24 models
H24=24
VAL_PARQUET_H24="data/processed/val_H${H24}.parquet"
VAL_CSV_H24="data/val/${TASK}_H${H24}_VAL.csv"
A_MODEL_H24="${MODELS_DIR}/${TASK}_ADAUSDT_and_2_more_H${H24}.joblib"
B_MODEL_H24="${MODELS_DIR}/${TASK}_PNUTUSDT_and_6_more_H${H24}.joblib"

echo "=== TRAIN A H12 ==="
python scripts/train_forecasters.py \
  --symbols "${A_SYMBOLS}" --task "${TASK}" --hbars "${H12}" \
  --entry_mode "${ENTRY}" ${FLAGS} --models_dir "${MODELS_DIR}"

echo "=== TRAIN B H12 ==="
python scripts/train_forecasters.py \
  --symbols "${B_SYMBOLS}" --task "${TASK}" --hbars "${H12}" \
  --entry_mode "${ENTRY}" ${FLAGS} --models_dir "${MODELS_DIR}"

echo "=== TRAIN A H24 ==="
python scripts/train_forecasters.py \
  --symbols "${A_SYMBOLS}" --task "${TASK}" --hbars "${H24}" \
  --entry_mode "${ENTRY}" ${FLAGS} --models_dir "${MODELS_DIR}"

echo "=== TRAIN B H24 ==="
python scripts/train_forecasters.py \
  --symbols "${B_SYMBOLS}" --task "${TASK}" --hbars "${H24}" \
  --entry_mode "${ENTRY}" ${FLAGS} --models_dir "${MODELS_DIR}"

echo "=== PREP VAL CSV H12 ==="
mkdir -p data/val
python - <<PY
import pandas as pd
p_in="${VAL_PARQUET_H12}"; p_out="${VAL_CSV_H12}"
df=pd.read_parquet(p_in)
assert "y" in df.columns, "val parquet H12 must have column 'y'"
df.to_csv(p_out, index=False)
print("Wrote", p_out, df.shape)
PY

echo "=== PREP VAL CSV H24 ==="
python - <<PY
import pandas as pd
p_in="${VAL_PARQUET_H24}"; p_out="${VAL_CSV_H24}"
df=pd.read_parquet(p_in)
assert "y" in df.columns, "val parquet H24 must have column 'y'"
df.to_csv(p_out, index=False)
print("Wrote", p_out, df.shape)
PY

echo "=== CALIB A H12 ==="
python scripts/calibrate_forecasters.py \
  --model_path "${A_MODEL_H12}" \
  --val_csv "${VAL_CSV_H12}" \
  --kind isotonic

echo "=== CALIB B H12 ==="
python scripts/calibrate_forecasters.py \
  --model_path "${B_MODEL_H12}" \
  --val_csv "${VAL_CSV_H12}" \
  --kind isotonic

echo "=== CALIB A H24 ==="
python scripts/calibrate_forecasters.py \
  --model_path "${A_MODEL_H24}" \
  --val_csv "${VAL_CSV_H24}" \
  --kind isotonic

echo "=== CALIB B H24 ==="
python scripts/calibrate_forecasters.py \
  --model_path "${B_MODEL_H24}" \
  --val_csv "${VAL_CSV_H24}" \
  --kind isotonic

echo "=== GEN MODELS YAML ENSEMBLE ==="
python scripts/gen_models_yaml.py \
  --a12 "${A_MODEL_H12}" --b12 "${B_MODEL_H12}" \
  --a24 "${A_MODEL_H24}" --b24 "${B_MODEL_H24}" \
  --out config/models.yaml

echo "✅ ENSEMBLE PIPELINE DONE"
