# scripts/gen_models_yaml_optimized.py
from __future__ import annotations
import argparse, os, glob, json
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

def _get_model_quality(model_path: str) -> float:
    """Читает AUC из meta.json для определения качества модели."""
    meta_path = model_path.replace(".joblib", ".meta.json")
    try:
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        return meta.get("val_auc", 0.5)
    except:
        return 0.5

def main():
    ap = argparse.ArgumentParser(description="Generate optimized config/models_individual.yaml with quality-based weights.")
    ap.add_argument("--symbols", required=True, help="Comma-separated list of symbols")
    ap.add_argument("--out", default="config/models_individual_optimized.yaml")
    ap.add_argument("--models_dir", default="forecast/models")
    ap.add_argument("--min_auc", type=float, default=0.45, help="Minimum AUC to enable model")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    # Качество моделей по парам (из анализа)
    quality_data = {
        "ADAUSDT": {"H12": 0.541, "H24": 0.528},
        "HBARUSDT": {"H12": 0.491, "H24": 0.509},
        "LTCUSDT": {"H12": 0.558, "H24": 0.554},
        "PNUTUSDT": {"H12": 0.475, "H24": 0.521},
        "WIFUSDT": {"H12": 0.559, "H24": 0.448},
        "ENAUSDT": {"H12": 0.427, "H24": 0.427},
        "DOGEUSDT": {"H12": 0.574, "H24": 0.571},
        "ARBUSDT": {"H12": 0.556, "H24": 0.554},
        "SUIUSDT": {"H12": 0.585, "H24": 0.451},
        "SEIUSDT": {"H12": 0.573, "H24": 0.543}
    }

    # Функция для расчета весов на основе качества
    def calculate_weights(h12_auc: float, h24_auc: float) -> tuple:
        """Рассчитывает оптимальные веса H12/H24 на основе AUC."""
        total_auc = h12_auc + h24_auc
        
        # Если оба слабые - отключаем
        if total_auc < 0.9:  # 0.45 + 0.45
            return 0.0, 0.0
        
        # Если один слабый - даем больше веса сильному
        if h12_auc - h24_auc > 0.05:  # H12 значительно лучше
            return 0.8, 0.2
        elif h24_auc - h12_auc > 0.05:  # H24 значительно лучше
            return 0.2, 0.8
        else:  # Примерно равные
            return 0.5, 0.5

    # Создаем конфигурацию для каждого символа
    models_config = {}
    disabled_symbols = []
    
    for symbol in symbols:
        if symbol not in quality_data:
            print(f"⚠️ No quality data for {symbol}, using default weights")
            models_config[symbol] = {
                "H12": {
                    "path": f"{args.models_dir}/binary_hit_{symbol}_H12.joblib",
                    "calibrator": None,
                    "calibrator_prefer": "isotonic",
                    "prob_weight_base": 1.0,
                    "prob_weight_gain": 1.15,
                    "enabled": True,
                    "weight": 0.5
                },
                "H24": {
                    "path": f"{args.models_dir}/binary_hit_{symbol}_H24.joblib",
                    "calibrator": None,
                    "calibrator_prefer": "isotonic",
                    "prob_weight_base": 1.0,
                    "prob_weight_gain": 1.15,
                    "enabled": True,
                    "weight": 0.5
                }
            }
            continue

        h12_auc = quality_data[symbol]["H12"]
        h24_auc = quality_data[symbol]["H24"]
        
        w12, w24 = calculate_weights(h12_auc, h24_auc)
        
        # Проверяем минимальный AUC
        if h12_auc < args.min_auc and h24_auc < args.min_auc:
            print(f"🚫 Disabling {symbol}: both horizons below min AUC ({args.min_auc})")
            disabled_symbols.append(symbol)
            continue
        
        # Отключаем слабые горизонты
        h12_enabled = h12_auc >= args.min_auc
        h24_enabled = h24_auc >= args.min_auc
        
        if not h12_enabled and not h24_enabled:
            print(f"🚫 Disabling {symbol}: no horizons above min AUC")
            disabled_symbols.append(symbol)
            continue
        
        models_config[symbol] = {
            "H12": {
                "path": f"{args.models_dir}/binary_hit_{symbol}_H12.joblib",
                "calibrator": None,  # Будет заполнено после калибровки
                "calibrator_prefer": "isotonic",
                "prob_weight_base": 1.0,
                "prob_weight_gain": 1.15,
                "enabled": h12_enabled,
                "weight": w12 if h12_enabled else 0.0,
                "auc": h12_auc
            },
            "H24": {
                "path": f"{args.models_dir}/binary_hit_{symbol}_H24.joblib",
                "calibrator": None,  # Будет заполнено после калибровки
                "calibrator_prefer": "isotonic",
                "prob_weight_base": 1.0,
                "prob_weight_gain": 1.15,
                "enabled": h24_enabled,
                "weight": w24 if h24_enabled else 0.0,
                "auc": h24_auc
            }
        }
        
        print(f"✅ {symbol}: H12={h12_auc:.3f}(w={w12:.1f}) H24={h24_auc:.3f}(w={w24:.1f})")

    # Создаем финальную конфигурацию
    cfg = {
        "ml": {
            "enabled": True,
            "min_auc_threshold": args.min_auc,
            "disabled_symbols": disabled_symbols,
            "models": models_config,
            "ensemble": {
                "enabled": True,
                "default_weights": {"H12": 0.5, "H24": 0.5},
                "quality_based_weights": True
            },
            "fail_safes": {
                "disable_weak_horizons": True,
                "min_horizon_auc_diff": 0.05,
                "max_ensemble_weight": 0.8
            }
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    
    print(f"\n📊 Summary:")
    print(f"  Total symbols: {len(symbols)}")
    print(f"  Enabled symbols: {len(models_config)}")
    print(f"  Disabled symbols: {len(disabled_symbols)}")
    if disabled_symbols:
        print(f"  Disabled: {', '.join(disabled_symbols)}")
    print(f"  Config written to: {args.out}")

if __name__ == "__main__":
    main()
