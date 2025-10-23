# scripts/gen_models_yaml.py
from __future__ import annotations
import argparse, os, glob
import yaml  # pip install pyyaml

def _calib_path(model_path: str) -> str | None:
    """Ищем рядом *.calib.isotonic.joblib или *.calib.platt.joblib (в приоритете isotonic)."""
    base = model_path.rsplit(".joblib", 1)[0]
    iso = base + ".calib.isotonic.joblib"
    pla = base + ".calib.platt.joblib"
    if os.path.exists(iso):
        return iso
    if os.path.exists(pla):
        return pla
    return None

def main():
    ap = argparse.ArgumentParser(description="Generate config/models.yaml for A/B groups with H12+H24 ensemble.")
    ap.add_argument("--a12", required=True)
    ap.add_argument("--b12", required=True)
    ap.add_argument("--a24", required=True)
    ap.add_argument("--b24", required=True)
    ap.add_argument("--out", default="config/models.yaml")
    ap.add_argument("--w12", type=float, default=0.5, help="Weight for H12 in ensemble")
    ap.add_argument("--w24", type=float, default=0.5, help="Weight for H24 in ensemble")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    cfg = {
        "ml": {
            "enabled": True,
            "models": {
                "A_group": {
                    "H12": {
                        "path": args.a12,
                        "calibrator": _calib_path(args.a12),
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.15
                    },
                    "H24": {
                        "path": args.a24,
                        "calibrator": _calib_path(args.a24),
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.15
                    }
                },
                "B_group": {
                    "H12": {
                        "path": args.b12,
                        "calibrator": _calib_path(args.b12),
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.25
                    },
                    "H24": {
                        "path": args.b24,
                        "calibrator": _calib_path(args.b24),
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.25
                    }
                }
            },
            "ensemble": {
                "enabled": True,
                "weights": {"H12": float(args.w12), "H24": float(args.w24)}
            }
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
