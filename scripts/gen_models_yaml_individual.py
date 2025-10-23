# scripts/gen_models_yaml_individual.py
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
    ap = argparse.ArgumentParser(description="Generate config/models_individual.yaml for individual symbol models.")
    ap.add_argument("--symbols", required=True, help="Comma-separated list of symbols")
    ap.add_argument("--out", default="config/models_individual.yaml")
    ap.add_argument("--models_dir", default="forecast/models")
    ap.add_argument("--w12", type=float, default=0.5, help="Weight for H12 in ensemble")
    ap.add_argument("--w24", type=float, default=0.5, help="Weight for H24 in ensemble")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    # Создаем конфигурацию для каждого символа
    models_config = {}
    
    for symbol in symbols:
        models_config[symbol] = {
            "H12": {
                "path": f"{args.models_dir}/binary_hit_{symbol}_H12.joblib",
                "calibrator": None,  # Будет заполнено ниже
                "calibrator_prefer": "isotonic",
                "prob_weight_base": 1.0,
                "prob_weight_gain": 1.15
            },
            "H24": {
                "path": f"{args.models_dir}/binary_hit_{symbol}_H24.joblib",
                "calibrator": None,  # Будет заполнено ниже
                "calibrator_prefer": "isotonic",
                "prob_weight_base": 1.0,
                "prob_weight_gain": 1.15
            }
        }
        
        # Ищем калибраторы
        for horizon in ["H12", "H24"]:
            model_path = models_config[symbol][horizon]["path"]
            calib_path = _calib_path(model_path)
            if calib_path:
                models_config[symbol][horizon]["calibrator"] = calib_path

    cfg = {
        "ml": {
            "enabled": True,
            "models": models_config,
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
