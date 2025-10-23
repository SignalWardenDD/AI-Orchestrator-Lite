# scripts/calibrate_forecasters.py
from __future__ import annotations
import os, json, argparse
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

try:
    import joblib
    SK_OK = True
except Exception:
    SK_OK = False

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.forecast.calibrators import Calibrator, calibration_report

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _load_model(model_path: str):
    if not SK_OK:
        raise RuntimeError("joblib not available; cannot load model. Install scikit-learn to enable calibration.")
    obj = joblib.load(model_path)
    return obj["model"], obj.get("meta", {})

def _predict_raw(model, kind: str, X: pd.DataFrame) -> np.ndarray:
    if kind.startswith("lgb"):
        # LightGBM booster has .predict
        return model.predict(X)
    elif kind.startswith("sk_"):
        return model.predict_proba(X)[:, 1]
    elif kind.startswith("linear_fallback"):
        w = np.asarray(model["weights"])
        # align columns if present
        names = model.get("feature_names", list(X.columns))
        X1 = X[names].values if set(names).issubset(set(X.columns)) else X.values
        s = X1 @ w[:X1.shape[1]]
        # scale to 0..1
        if np.max(s) - np.min(s) < 1e-9:
            return np.full_like(s, 0.5)
        return (s - s.min()) / (s.max() - s.min() + 1e-12)
    else:
        raise ValueError(f"Unknown model kind for raw prediction: {kind}")

def main():
    ap = argparse.ArgumentParser(description="Fit probability calibrator (Platt/Isotonic) for a saved model.")
    ap.add_argument("--model_path", required=True, type=str)
    ap.add_argument("--val_csv", required=True, type=str, help="CSV with validation features and target y (0/1).")
    ap.add_argument("--kind", type=str, default="platt", choices=["platt","isotonic"])
    ap.add_argument("--out_dir", type=str, default=None)
    args = ap.parse_args()

    if not SK_OK:
        print(json.dumps({"ok": False, "error": "scikit-learn/joblib required for calibration"}, ensure_ascii=False))
        return

    model, meta = _load_model(args.model_path)
    kind = meta.get("kind", "sk_logreg")
    feat_names = meta.get("feature_names", None)

    df = pd.read_csv(args.val_csv)
    if "y" not in df.columns:
        raise ValueError("val_csv must contain binary target column 'y'")
    y = df["y"].astype(int).values
    X = df.drop(columns=["y"])
    if feat_names and set(feat_names).issubset(set(X.columns)):
        X = X[feat_names]

    raw = _predict_raw(model, kind=meta.get("kind","sk_logreg"), X=X).astype(float)

    # отчёт до/после
    rep = calibration_report(raw_scores=raw, y_true=y, kind=args.kind, bins=10)

    # обучаем и сохраняем
    calib = Calibrator(kind=args.kind).fit(raw, y)
    out_dir = args.out_dir or os.path.dirname(args.model_path)
    _ensure_dir(out_dir)
    calib_path = os.path.join(out_dir, os.path.basename(args.model_path).replace(".joblib", f".calib.{args.kind}.joblib"))
    calib.save(calib_path)

    print(json.dumps({
        "ok": True,
        "calibrator_path": calib_path,
        "report": rep
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()