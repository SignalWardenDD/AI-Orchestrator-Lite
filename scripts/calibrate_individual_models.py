# scripts/calibrate_individual_models.py
from __future__ import annotations
import argparse, os, glob, json
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import sys

# Добавляем путь к проекту
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.forecast.calibrators import Calibrator

def _load_validation_data(symbol: str, horizon: int, data_dir: str = "data/processed") -> pd.DataFrame:
    """Загружает валидационные данные для символа и горизонта."""
    val_file = f"{data_dir}/val_H{horizon}.parquet"
    
    if not os.path.exists(val_file):
        print(f"⚠️ Validation file not found: {val_file}")
        return None
    
    try:
        df = pd.read_parquet(val_file)
        
        # Фильтруем данные для конкретного символа если есть колонка symbol
        if 'symbol' in df.columns:
            df = df[df['symbol'] == symbol]
        
        if len(df) == 0:
            print(f"⚠️ No validation data for {symbol} in {val_file}")
            return None
            
        return df
    except Exception as e:
        print(f"❌ Failed to load validation data for {symbol}: {e}")
        return None

def _create_dummy_validation_data(symbol: str, horizon: int, n_samples: int = 1000) -> pd.DataFrame:
    """Создает тестовые валидационные данные для калибровки."""
    np.random.seed(42)
    
    # Создаем случайные фичи (17 колонок как в моделях)
    feature_names = [
        'ret_1', 'ret_3', 'ret_6', 'ema20', 'ema50', 'ema200', 'ema20_slope',
        'natr14', 'rng_1', 'rng_3', 'z_close_50', 'ret_1_lag1', 'rng_1_lag1',
        'ret_1_lag2', 'rng_1_lag2', 'ret_1_lag3', 'rng_1_lag3'
    ]
    
    X = np.random.randn(n_samples, len(feature_names))
    y = np.random.randint(0, 2, n_samples)
    
    df = pd.DataFrame(X, columns=feature_names)
    df['y'] = y
    df['symbol'] = symbol
    
    return df

def calibrate_model(symbol: str, horizon: int, model_path: str, 
                   val_data: pd.DataFrame = None, kind: str = "isotonic") -> str:
    """Калибрует модель для символа и горизонта."""
    
    # Загружаем модель
    try:
        import joblib
        model_data = joblib.load(model_path)
        model = model_data["model"]
        meta = model_data["meta"]
    except Exception as e:
        print(f"❌ Failed to load model {model_path}: {e}")
        return None
    
    # Подготавливаем валидационные данные
    if val_data is None:
        print(f"📊 Creating dummy validation data for {symbol} H{horizon}")
        val_data = _create_dummy_validation_data(symbol, horizon)
    
    # Извлекаем фичи и таргеты
    feature_names = meta.get("feature_names", [])
    X_val = val_data[feature_names].values
    y_val = val_data['y'].values
    
    # Получаем raw scores от модели
    try:
        if hasattr(model, 'predict_proba'):
            raw_scores = model.predict_proba(X_val)[:, 1]
        else:
            raw_scores = model.predict(X_val)
    except Exception as e:
        print(f"❌ Failed to get predictions from model: {e}")
        return None
    
    # Обучаем калибратор
    try:
        calibrator = Calibrator(kind=kind)
        calibrator.fit(raw_scores, y_val)
        
        # Сохраняем калибратор
        calib_path = model_path.replace(".joblib", f".calib.{kind}.joblib")
        calibrator.save(calib_path)
        
        # Генерируем отчет калибровки
        from orchestrator.forecast.calibrators import calibration_report
        report = calibration_report(raw_scores, y_val, kind=kind)
        print(f"✅ Calibrated {symbol} H{horizon}: ECE={report['ece_after']:.4f}, Brier={report['brier_after']:.4f}")
        
        return calib_path
        
    except Exception as e:
        print(f"❌ Failed to calibrate {symbol} H{horizon}: {e}")
        return None

def main():
    ap = argparse.ArgumentParser(description="Calibrate individual models for all symbols and horizons.")
    ap.add_argument("--symbols", required=True, help="Comma-separated list of symbols")
    ap.add_argument("--models_dir", default="forecast/models")
    ap.add_argument("--val_data_dir", default="data/processed")
    ap.add_argument("--kind", default="isotonic", choices=["isotonic", "platt"])
    ap.add_argument("--horizons", default="12,24", help="Comma-separated horizons")
    ap.add_argument("--use_dummy", action="store_true", help="Use dummy validation data")
    
    args = ap.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    horizons = [int(h.strip()) for h in args.horizons.split(",") if h.strip()]
    
    print(f"🔧 Calibrating individual models")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Horizons: {', '.join(map(str, horizons))}")
    print(f"  Method: {args.kind}")
    print()
    
    results = {}
    
    for symbol in symbols:
        results[symbol] = {}
        
        for horizon in horizons:
            model_path = f"{args.models_dir}/binary_hit_{symbol}_H{horizon}.joblib"
            
            if not os.path.exists(model_path):
                print(f"⚠️ Model not found: {model_path}")
                results[symbol][f"H{horizon}"] = None
                continue
            
            print(f"🎯 Calibrating {symbol} H{horizon}...")
            
            # Загружаем валидационные данные
            val_data = None
            if not args.use_dummy:
                val_data = _load_validation_data(symbol, horizon, args.val_data_dir)
                if val_data is None:
                    print(f"📊 Using dummy data for {symbol} H{horizon}")
                    val_data = _create_dummy_validation_data(symbol, horizon)
            else:
                val_data = _create_dummy_validation_data(symbol, horizon)
            
            # Калибруем
            calib_path = calibrate_model(symbol, horizon, model_path, val_data, args.kind)
            results[symbol][f"H{horizon}"] = calib_path
    
    # Сводка результатов
    print(f"\n📊 Calibration Summary:")
    total_models = len(symbols) * len(horizons)
    successful = sum(1 for sym_results in results.values() 
                    for calib_path in sym_results.values() 
                    if calib_path is not None)
    
    print(f"  Total models: {total_models}")
    print(f"  Successfully calibrated: {successful}")
    print(f"  Failed: {total_models - successful}")
    
    for symbol, sym_results in results.items():
        for horizon, calib_path in sym_results.items():
            status = "✅" if calib_path else "❌"
            print(f"  {status} {symbol} {horizon}: {calib_path or 'Failed'}")

if __name__ == "__main__":
    main()
