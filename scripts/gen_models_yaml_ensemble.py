# scripts/gen_models_yaml_ensemble.py
from __future__ import annotations
import argparse, os, json, sys
from pathlib import Path
import yaml

def main():
    ap = argparse.ArgumentParser(description="Generate models config with ensemble support")
    ap.add_argument("--a_model_h12", required=True, help="A group model for H12")
    ap.add_argument("--b_model_h12", required=True, help="B group model for H12")
    ap.add_argument("--a_model_h24", required=True, help="A group model for H24")
    ap.add_argument("--b_model_h24", required=True, help="B group model for H24")
    ap.add_argument("--a_calib_h12", required=True, help="A group calibrator for H12")
    ap.add_argument("--b_calib_h12", required=True, help="B group calibrator for H12")
    ap.add_argument("--a_calib_h24", required=True, help="A group calibrator for H24")
    ap.add_argument("--b_calib_h24", required=True, help="B group calibrator for H24")
    ap.add_argument("--out", default="config/models.yaml")
    ap.add_argument("--ensemble", action="store_true", help="Enable ensemble mode")
    args = ap.parse_args()

    if args.ensemble:
        cfg = {
            "ml": {
                "enabled": True,
                "models": {
                    "A_group_H12": {
                        "path": args.a_model_h12,
                        "calibrator": args.a_calib_h12,
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.2,
                        "horizon": 12
                    },
                    "B_group_H12": {
                        "path": args.b_model_h12,
                        "calibrator": args.b_calib_h12,
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.2,
                        "horizon": 12
                    },
                    "A_group_H24": {
                        "path": args.a_model_h24,
                        "calibrator": args.a_calib_h24,
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.2,
                        "horizon": 24
                    },
                    "B_group_H24": {
                        "path": args.b_model_h24,
                        "calibrator": args.b_calib_h24,
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.2,
                        "horizon": 24
                    }
                },
                "ensemble": {
                    "enabled": True,
                    "horizons": [12, 24],
                    "weights": {
                        "H12": 0.3,
                        "H24": 0.7
                    },
                    "group_weights": {
                        "A_group": 0.5,
                        "B_group": 0.5
                    }
                }
            }
        }
    else:
        # Single horizon mode
        cfg = {
            "ml": {
                "enabled": True,
                "models": {
                    "A_group": {
                        "path": args.a_model_h24,  # Use H24 as default
                        "calibrator": args.a_calib_h24,
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.2
                    },
                    "B_group": {
                        "path": args.b_model_h24,  # Use H24 as default
                        "calibrator": args.b_calib_h24,
                        "calibrator_prefer": "isotonic",
                        "prob_weight_base": 1.0,
                        "prob_weight_gain": 1.2
                    }
                },
                "ensemble": {
                    "enabled": False,
                    "weights": {"A_group": 0.5, "B_group": 0.5}
                }
            }
        }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"Wrote {args.out}")
    print(f"Ensemble mode: {args.ensemble}")

if __name__ == "__main__":
    main()
