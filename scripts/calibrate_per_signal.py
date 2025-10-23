#!/usr/bin/env python3
"""
Калибровка per-signal моделей.
"""

import json
import argparse
import joblib
from pathlib import Path
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

# Добавляем путь к проекту
import sys
sys.path.append('.')

from orchestrator.data.loader import load_features_df, load_kline_df, load_signal_marks_df
from orchestrator.forecast.labeling import make_binary_hit_labels

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models_root", default="forecast/models/per_signal")
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--horizons", nargs="+", default=["H12","H24"])
    ap.add_argument("--signals", nargs="+", default=["BRK","PB","MR","BB"])
    args = ap.parse_args()

    root = Path(args.models_root)

    for sym in args.symbols:
        feats = load_features_df(sym)
        marks = load_signal_marks_df(sym)
        kline = load_kline_df(sym)
        for sig in args.signals:
            df = feats.join(marks[args.signals], how="inner")
            df = df[df[sig] == 1].copy()
            if df.empty: 
                print(f"[SKIP] {sym}/{sig}: no rows")
                continue
            for hz in args.horizons:
                lbl = make_binary_hit_labels(kline, hz)
                y = lbl.reindex(df.index).dropna().astype(int).values
                Xidx = df.index[-len(y):]  # согласуем длину
                # грузим модель
                mpath = root / sym / sig / f"binary_hit_{sym}_{sig}_{hz}.joblib"
                if not mpath.exists():
                    continue
                bundle = joblib.load(mpath)
                model = bundle["model"]; feature_names = bundle["feature_names"]
                p = model.predict_proba(df.loc[Xidx, feature_names].values)[:,1]
                iso = IsotonicRegression(out_of_bounds="clip").fit(p, y)
                joblib.dump(iso, root / sym / sig / f"binary_hit_{sym}_{sig}_{hz}.calib.isotonic.joblib")
                print(f"[CAL] {sym}/{sig}/{hz}  Brier={brier_score_loss(y, iso.predict(p)):.4f}")

if __name__ == "__main__":
    main()
