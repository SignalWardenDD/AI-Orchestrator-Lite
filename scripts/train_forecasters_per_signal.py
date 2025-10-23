#!/usr/bin/env python3
"""
Обучение per-signal моделей для каждой пары и типа сигнала.
"""

import json
import os
import argparse
import joblib
import numpy as np
from pathlib import Path
from datetime import datetime
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

# Добавляем путь к проекту
import sys
sys.path.append('.')

from orchestrator.signals.types import SIGNAL_TYPES, DEFAULT_HORIZONS
from orchestrator.utils.seed import set_seed
from orchestrator.utils.io import ensure_dir
from orchestrator.forecast.calibration import fit_isotonic
from orchestrator.forecast.labeling import make_binary_hit_labels
from orchestrator.data.loader import load_features_df, load_kline_df, load_signal_marks_df

def build_dataset_for(symbol: str, signal: str, horizon: str, feature_names: list[str], random_state=42):
    """
    Фильтруем строки только там, где сработал `signal`.
    """
    feats = load_features_df(symbol)                 # индекс по времени, есть 17+ колонок
    marks = load_signal_marks_df(symbol)             # бинарные флаги с тем же индексом/временем
    df = feats.join(marks[SIGNAL_TYPES], how="inner")  # совмещаем по времени
    df = df[df[signal] == 1].copy()
    if df.empty or len(df) < 500:
        raise RuntimeError(f"[{symbol}][{signal}][{horizon}] too few samples: {len(df)}")

    # Лейбл: hit TP раньше SL в горизонте N баров. Используем твой лейблер.
    kline = load_kline_df(symbol)
    lbl = make_binary_hit_labels(kline, horizon)     # вернёт Series 0/1, индекс по времени
    df["y"] = lbl.reindex(df.index).astype("Int64")
    df = df.dropna(subset=["y"])
    X = df[feature_names].values
    y = df["y"].values.astype(int)
    return X, y, df.index

def train_one(symbol, signal, horizon, out_dir, feature_names, test_size=0.25, rs=42):
    X, y, idx = build_dataset_for(symbol, signal, horizon, feature_names, rs)
    Xtr, Xva, ytr, yva = train_test_split(X, y, test_size=test_size, random_state=rs, stratify=y)

    model = LGBMClassifier(
        n_estimators=600,
        learning_rate=0.03,
        max_depth=-1,
        num_leaves=63,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=4.0,
        min_child_samples=40,
        n_jobs=-1,
        random_state=rs,
    )
    model.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="auc", verbose=False)
    p = model.predict_proba(Xva)[:,1]
    auc = roc_auc_score(yva, p)

    # Сохраняем модель
    ensure_dir(out_dir)
    model_path = out_dir / f"binary_hit_{symbol}_{signal}_{horizon}.joblib"
    joblib.dump({"model": model, "feature_names": feature_names}, model_path)

    meta = {
        "task": "binary_hit",
        "symbol": symbol,
        "signal": signal,
        "horizon": horizon,
        "feature_names": feature_names,
        "metrics": {"val_auc": float(auc), "n_train": int(len(y))},
        "created_at": datetime.utcnow().isoformat()+"Z",
        "tp_mult_atr": 2.0, "sl_mult_atr": 2.0
    }
    with open(out_dir / f"binary_hit_{symbol}_{signal}_{horizon}.meta.json","w") as f:
        json.dump(meta, f, indent=2)

    # Калибровка (изотоника)
    calib = fit_isotonic(p, yva)
    joblib.dump(calib, out_dir / f"binary_hit_{symbol}_{signal}_{horizon}.calib.isotonic.joblib")

    return auc, len(y), str(model_path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True, help="e.g. ADAUSDT HBARUSDT ...")
    ap.add_argument("--horizons", nargs="+", default=list(DEFAULT_HORIZONS))
    ap.add_argument("--signals", nargs="+", default=list(SIGNAL_TYPES))
    ap.add_argument("--out_root", default="forecast/models/per_signal")
    ap.add_argument("--feature_names", nargs="+", default=[
        "ret_1","ret_3","ret_6","ema20","ema50","ema200","ema20_slope",
        "natr14","rng_1","rng_3","z_close_50",
        "ret_1_lag1","ret_1_lag2","ret_1_lag3",
        "rng_1_lag1","rng_1_lag2","rng_1_lag3"
    ])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    set_seed(args.seed)
    root = Path(args.out_root)

    report = []
    for sym in args.symbols:
        for sig in args.signals:
            for hz in args.horizons:
                out_dir = root / sym / sig
                try:
                    auc, nrows, path = train_one(sym, sig, hz, out_dir, args.feature_names, rs=args.seed)
                    report.append({"symbol": sym, "signal": sig, "horizon": hz, "auc": auc, "rows": nrows, "path": path})
                    print(f"[OK] {sym}/{sig}/{hz}: AUC={auc:.3f} rows={nrows}")
                except Exception as e:
                    print(f"[SKIP] {sym}/{sig}/{hz}: {e}")

    # Итоговый отчёт
    with open(root / "_train_report.json","w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    main()
