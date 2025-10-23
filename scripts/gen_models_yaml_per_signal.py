#!/usr/bin/env python3
"""
Генерация YAML-карты для per-signal моделей.
"""

import argparse
import json
from pathlib import Path

# Добавляем путь к проекту
import sys
sys.path.append('.')

from orchestrator.signals.types import SIGNAL_TYPES, DEFAULT_HORIZONS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models_root", default="forecast/models/per_signal")
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--horizons", nargs="+", default=list(DEFAULT_HORIZONS))
    ap.add_argument("--signals", nargs="+", default=list(SIGNAL_TYPES))
    ap.add_argument("--out_yaml", default="config/models_per_signal.yaml")
    args = ap.parse_args()

    root = Path(args.models_root)
    cfg = {}
    for sym in args.symbols:
        cfg[sym] = {}
        for sig in args.signals:
            cfg[sym][sig] = {}
            for hz in args.horizons:
                base = root / sym / sig / f"binary_hit_{sym}_{sig}_{hz}"
                model_path = f"{base}.joblib"
                calib_path = f"{base}.calib.isotonic.joblib"
                meta_path  = f"{base}.meta.json"
                if not Path(model_path).exists() or not Path(meta_path).exists():
                    continue
                with open(meta_path) as f:
                    meta = json.load(f)
                # дефолтные веса по качеству
                auc = float(meta.get("metrics",{}).get("val_auc", 0.50))
                weight = 1.0 if auc >= 0.55 else (0.8 if auc >= 0.52 else 0.6)
                cfg[sym][sig][hz] = {
                    "model_path": model_path,
                    "calibrator_path": calib_path if Path(calib_path).exists() else None,
                    "feature_names": meta.get("feature_names"),
                    "weights": weight,
                    "ev_min": 0.10  # можно тонко настроить по сигналам
                }
    import yaml
    with open(args.out_yaml, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=True)
    print(f"Written: {args.out_yaml}")

if __name__ == "__main__":
    main()
