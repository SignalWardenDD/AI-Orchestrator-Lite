# scripts/train_forecasters_individual.py
from __future__ import annotations
import os, json, argparse, warnings
from dataclasses import asdict, dataclass
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd

# Optional ML deps
try:
    import lightgbm as lgb
    LGB_OK = True
except Exception:
    LGB_OK = False

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import roc_auc_score
    import joblib
    SK_OK = True
except Exception:
    SK_OK = False

# Project modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.utils.mathx import natr, atr, ewma, zscore, pct_change_safe, EPS
from orchestrator.forecast.labeling import HorizonSpec, build_labels, build_labels_open_entry

# Используем реальные данные
fetch_ohlcv = None

# Функция для загрузки реальных данных
def _load_real_data(symbol: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Загружает реальные данные из CSV файлов."""
    import glob
    
    # Ищем файлы данных для символа
    data_dir = "data/raw/binance_futures/1h"
    pattern = f"{data_dir}/{symbol}_1h_*.csv"
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"No data files found for {symbol} in {data_dir}")
    
    # Берем самый новый файл
    latest_file = max(files, key=os.path.getctime)
    print(f"Loading {symbol} from {latest_file}")
    
    # Загружаем данные
    df = pd.read_csv(latest_file)
    
    # Преобразуем в нужный формат
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.set_index('timestamp')
    
    # Переименовываем колонки если нужно
    if 'open' not in df.columns and 'Open' in df.columns:
        df = df.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Volume': 'volume'
        })
    
    # Фильтруем по датам если указаны
    if start:
        start_dt = pd.to_datetime(start, utc=True)
        df = df[df.index >= start_dt]
    
    if end:
        end_dt = pd.to_datetime(end, utc=True)
        df = df[df.index <= end_dt]
    
    # Оставляем только нужные колонки
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    df = df[required_cols]
    
    return df.sort_index()

# Заглушка для тестирования (оставляем как fallback)
def _create_dummy_data(symbol: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Создает тестовые данные для обучения."""
    import numpy as np
    from datetime import datetime, timedelta
    
    # Создаем 1000 баров данных
    dates = pd.date_range(start='2023-01-01', periods=1000, freq='1h')
    
    # Генерируем случайные OHLCV данные
    np.random.seed(42)
    base_price = 100.0
    
    data = []
    price = base_price
    
    for i, date in enumerate(dates):
        # Простая модель случайного блуждания
        change = np.random.normal(0, 0.02)  # 2% волатильность
        price *= (1 + change)
        
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        volume = np.random.uniform(1000, 10000)
        
        data.append({
            'open': price,
            'high': max(price, high),
            'low': min(price, low),
            'close': price,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=dates)
    return df

# -------------------------------

@dataclass
class TrainConfig:
    symbols: List[str]
    start: Optional[str] = None
    end: Optional[str] = None
    horizon_bars: int = 24
    tp_mult_atr: float = 2.0
    sl_mult_atr: float = 2.0
    side: str = "LONG"
    task: str = "binary_hit"
    models_dir: str = "forecast/models"
    features_dir: str = "data/cache"
    train_ratio: float = 0.8
    random_state: int = 42

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _fetch_ohlc_or_die(symbol: str, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    if fetch_ohlcv is not None:
        try:
            df = fetch_ohlcv(symbol, start=start, end=end)
        except TypeError:
            df = fetch_ohlcv(symbol)
    else:
        # Используем реальные данные
        try:
            print(f"Loading real data for {symbol}")
            df = _load_real_data(symbol, start=start, end=end)
        except Exception as e:
            print(f"Failed to load real data for {symbol}: {e}")
            print(f"Using dummy data for {symbol}")
            df = _create_dummy_data(symbol, start=start, end=end)
    
    # ожидаем колонки: open, high, low, close, volume; индекс — datetime
    for c in ("open","high","low","close"):
        if c not in df.columns:
            raise ValueError(f"{symbol}: missing OHLC column {c}")
    if not isinstance(df.index, (pd.DatetimeIndex,)):
        if "timestamp" in df.columns:
            df = df.set_index(pd.to_datetime(df["timestamp"], utc=True)).drop(columns=["timestamp"])
        else:
            raise ValueError("OHLC must have DatetimeIndex or 'timestamp' column.")
    return df.sort_index()

def _simple_features(ohlc: pd.DataFrame) -> pd.DataFrame:
    """Независимая от проекта фича-сетка: базовые техиндикаторы."""
    close = ohlc["close"]
    high, low = ohlc["high"], ohlc["low"]
    feat = pd.DataFrame(index=ohlc.index)
    
    # Returns
    feat["ret_1"] = pct_change_safe(close, 1)
    feat["ret_3"] = pct_change_safe(close, 3)
    feat["ret_6"] = pct_change_safe(close, 6)
    
    # EMAs
    feat["ema20"] = ewma(close, 20)
    feat["ema50"] = ewma(close, 50)
    feat["ema200"] = ewma(close, 200)
    feat["ema20_slope"] = pct_change_safe(feat["ema20"], 1)
    
    # Volatility
    feat["natr14"] = natr(high, low, close, 14)
    feat["rng_1"] = (high - low) / close.replace(0.0, np.nan)
    feat["rng_3"] = feat["rng_1"].rolling(3).mean()
    
    # Z-score
    diff = close - feat['ema50']
    rolling_mean = diff.rolling(50).mean()
    rolling_std = diff.rolling(50).std()
    feat['z_close_50'] = (diff - rolling_mean) / rolling_std.replace(0, np.nan)
    
    # Lags
    for k in (1,2,3):
        feat[f"ret_1_lag{k}"] = feat["ret_1"].shift(k)
        feat[f"rng_1_lag{k}"] = feat["rng_1"].shift(k)
    
    feat = feat.replace([np.inf, -np.inf], np.nan).dropna()
    return feat

def _align_xy(features: pd.DataFrame, labels: pd.Series) -> Tuple[pd.DataFrame, pd.Series]:
    df = features.join(labels.rename("y"), how="inner")
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    X = df.drop(columns=["y"])
    y = df["y"]
    return X, y

def _split_train_val(X: pd.DataFrame, y: pd.Series, ratio: float) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    n = len(X)
    cut = int(n * ratio)
    return X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]

def _train_estimator(X: pd.DataFrame, y: pd.Series, cfg: TrainConfig, Xva: pd.DataFrame = None, yva: pd.Series = None) -> Dict[str, Any]:
    """Возвращает словарь с ключами: kind, model_path, feature_names, metrics."""
    _ensure_dir(cfg.models_dir)

    # Бинаризация для некоторых задач
    if cfg.task in ("binary_hit", "direction", "trinary"):
        y_bin = y.copy()
        y_bin = (y_bin > 0).astype(int)
        if LGB_OK:
            dtrain = lgb.Dataset(X, label=y_bin, free_raw_data=False)
            dvalid = lgb.Dataset(Xva, label=yva, reference=dtrain, free_raw_data=False) if Xva is not None else None
            params = {
                "objective": "binary",
                "metric": ["auc", "binary_logloss"],
                "learning_rate": 0.035,
                "num_leaves": 31,
                "max_depth": -1,
                "min_data_in_leaf": 64,
                "feature_fraction": 0.75,
                "bagging_fraction": 0.8,
                "bagging_freq": 1,
                "lambda_l1": 1.0,
                "lambda_l2": 2.0,
                "seed": cfg.random_state,
                "verbosity": -1,
            }
            valid_sets = [dtrain]
            valid_names = ["train"]
            if dvalid is not None:
                valid_sets.append(dvalid)
                valid_names.append("valid")
            
            model = lgb.train(
                params, dtrain,
                num_boost_round=400,
                valid_sets=valid_sets,
                valid_names=valid_names,
                callbacks=[lgb.early_stopping(60)],
            )
            kind = "lgb_binary"
            model_obj = model
        elif SK_OK:
            pipe = Pipeline(steps=[
                ("scaler", StandardScaler(with_mean=False)),
                ("lr", LogisticRegression(max_iter=800, C=0.8, class_weight="balanced",
                                          n_jobs=None, random_state=cfg.random_state))
            ])
            model_obj = pipe.fit(X, y_bin)
            kind = "sk_logreg"
        else:
            weights = (X.corrwith(y)).fillna(0.0).values
            model_obj = {"weights": weights, "feature_names": list(X.columns)}
            kind = "linear_fallback"

    else:  # regression
        if LGB_OK:
            dtrain = lgb.Dataset(X, label=y)
            params = {
                "objective": "regression",
                "metric": ["l2", "l1"],
                "learning_rate": 0.05,
                "num_leaves": 31,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 1,
                "seed": cfg.random_state
            }
            model = lgb.train(params, dtrain, num_boost_round=300)
            kind = "lgb_reg"
            model_obj = model
        elif SK_OK:
            pipe = Pipeline(steps=[
                ("scaler", StandardScaler(with_mean=False)),
                ("lr", LogisticRegression(max_iter=500, random_state=cfg.random_state))
            ])
            y_bin = (y > 0).astype(int)
            model_obj = pipe.fit(X, y_bin)
            kind = "sk_logreg_reg_fallback"
        else:
            weights = (X.corrwith(y)).fillna(0.0).values
            model_obj = {"weights": weights, "feature_names": list(X.columns)}
            kind = "linear_fallback_reg"

    # Сохраняем
    meta = {
        "kind": kind,
        "feature_names": list(X.columns),
        "task": cfg.task,
        "horizon_bars": cfg.horizon_bars,
        "tp_mult_atr": cfg.tp_mult_atr,
        "sl_mult_atr": cfg.sl_mult_atr,
        "side": cfg.side,
    }

    # Имя файла для одного символа
    base = f"{cfg.task}_{cfg.symbols[0]}_H{cfg.horizon_bars}"
    model_path = os.path.join(cfg.models_dir, base + ".joblib")
    
    if SK_OK:
        joblib.dump({"model": model_obj, "meta": meta}, model_path)
    else:
        np.savez(model_path.replace(".joblib", ".npz"), **model_obj if isinstance(model_obj, dict) else {})
        with open(model_path.replace(".joblib", ".meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"kind": kind, "model_path": model_path, "feature_names": meta["feature_names"], "meta": meta}

def train_individual(symbol: str, cfg: TrainConfig) -> Dict[str, Any]:
    """Обучает модель для одного символа."""
    print(f"Training model for {symbol}...")
    
    # Загружаем данные для символа
    df = _fetch_ohlc_or_die(symbol, cfg.start, cfg.end)
    
    # Строим фичи
    feats = _simple_features(df)
    
    # ATR для барьеров
    atr_series = atr(df["high"], df["low"], df["close"], period=14).reindex(feats.index)
    horizon = HorizonSpec(cfg.horizon_bars, cfg.tp_mult_atr, cfg.sl_mult_atr)
    
    # Генерируем лейблы
    labels = build_labels(
        ohlc=df.loc[feats.index, ["open","high","low","close"]],
        atr_series=atr_series,
        horizon=horizon,
        task=cfg.task,
        side=cfg.side
    )
    
    # Выравниваем X, y
    X, y = _align_xy(feats, labels)
    
    if len(X) < 200:
        warnings.warn(f"Very small dataset for {symbol} (<200 rows). Consider expanding date range.")
    
    # Разделяем на train/val
    Xtr, Xva, ytr, yva = _split_train_val(X, y, cfg.train_ratio)
    
    # Обучаем модель
    cfg.symbols = [symbol]  # Для одного символа
    res = _train_estimator(Xtr, ytr, cfg, Xva, yva)
    
    # Быстрая метрика на валидации
    metrics: Dict[str, Any] = {}
    try:
        if res["kind"].startswith("lgb") and LGB_OK:
            model = joblib.load(res["model_path"]) if SK_OK else None
            if model:
                booster = model["model"]
                ypred = booster.predict(Xva, num_iteration=booster.best_iteration if hasattr(booster, "best_iteration") else None)
                auc = roc_auc_score((yva > 0).astype(int), ypred) if SK_OK else float("nan")
                metrics.update({"val_auc": float(auc), "val_count": int(yva.shape[0])})
        elif res["kind"] == "sk_logreg" and SK_OK:
            model = joblib.load(res["model_path"])
            ypred = model["model"].predict_proba(Xva)[:,1]
            auc = roc_auc_score((yva > 0).astype(int), ypred)
            metrics.update({"val_auc": float(auc), "val_count": int(yva.shape[0])})
    except Exception as e:
        metrics["val_note"] = f"metric_eval_failed: {e!r}"
    
    res["metrics"] = metrics
    
    # Сохраняем meta.json дополнительно
    meta_path = res["model_path"].replace(".joblib", ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({**res["meta"], **metrics}, f, ensure_ascii=False, indent=2)
    
    return res

def main():
    ap = argparse.ArgumentParser(description="Train individual forecaster models for each symbol.")
    ap.add_argument("--symbols", type=str, required=True, help="Comma-separated symbols")
    ap.add_argument("--start", type=str, default=None)
    ap.add_argument("--end", type=str, default=None)
    ap.add_argument("--task", type=str, default="binary_hit", choices=["binary_hit","direction","trinary","regression"])
    ap.add_argument("--side", type=str, default="LONG", choices=["LONG","SHORT"])
    ap.add_argument("--hbars", type=int, default=24)
    ap.add_argument("--tp_atr", type=float, default=2.0)
    ap.add_argument("--sl_atr", type=float, default=2.0)
    ap.add_argument("--models_dir", type=str, default="forecast/models")
    ap.add_argument("--train_ratio", type=float, default=0.8)
    ap.add_argument("--entry_mode", type=str, default="open_t", choices=["open_t", "close_t"])
    ap.add_argument("--both_sides", action="store_true", help="Train on both LONG and SHORT")
    ap.add_argument("--symbol_balance", action="store_true", help="Balance symbol weights")
    ap.add_argument("--corr_dropout", type=float, default=0.0, help="Correlation dropout rate")
    
    args = ap.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    
    results = []
    for symbol in symbols:
        cfg = TrainConfig(
            symbols=[symbol],
            start=args.start,
            end=args.end,
            horizon_bars=args.hbars,
            tp_mult_atr=args.tp_atr,
            sl_mult_atr=args.sl_atr,
            side=args.side,
            task=args.task,
            models_dir=args.models_dir,
            train_ratio=args.train_ratio,
        )
        
        _ensure_dir(cfg.models_dir)
        res = train_individual(symbol, cfg)
        results.append(res)
    
    print(json.dumps({
        "ok": True,
        "models_trained": len(results),
        "results": results
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
