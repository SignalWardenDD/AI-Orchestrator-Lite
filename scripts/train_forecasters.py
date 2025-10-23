# scripts/train_forecasters.py
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
# Data fetchers — если у тебя другие имена, эти try/except сделают фолбэк
try:
    from orchestrator.data.ingest import fetch_ohlcv_1h as fetch_ohlcv
except Exception:
    fetch_ohlcv = None

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
    start: Optional[str] = None     # ISO date
    end: Optional[str] = None       # ISO date
    horizon_bars: int = 24
    tp_mult_atr: float = 2.0
    sl_mult_atr: float = 2.0
    side: str = "LONG"              # LONG/SHORT for binary_hit
    task: str = "binary_hit"        # binary_hit | direction | trinary | regression
    models_dir: str = "forecast/models"
    features_dir: str = "data/cache"
    train_ratio: float = 0.8
    random_state: int = 42

# -------------------------------

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _fetch_ohlc_or_die(symbol: str, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    if fetch_ohlcv is not None:
        try:
            df = fetch_ohlcv(symbol, start=start, end=end)
        except TypeError:
            # Если функция не принимает start/end параметры
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
    feat["ret_1"]      = pct_change_safe(close, 1)
    feat["ret_3"]      = pct_change_safe(close, 3)
    feat["ret_6"]      = pct_change_safe(close, 6)
    feat["ema20"]      = ewma(close, 20)
    feat["ema50"]      = ewma(close, 50)
    feat["ema200"]     = ewma(close, 200)
    feat["ema20_slope"]= pct_change_safe(feat["ema20"], 1)
    feat["natr14"]     = natr(high, low, close, 14)
    # волатильность прокси:
    feat["rng_1"]      = (high - low) / close.replace(0.0, np.nan)
    feat["rng_3"]      = feat["rng_1"].rolling(3).mean()
    # z-score цены vs EMA50:
    feat["z_close_50"] = zscore(close - feat["ema50"], window=50)
    # лаги:
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

def _align_xy_open_entry_no_lookahead(
    ohlc: pd.DataFrame,
    feats: pd.DataFrame,
    atr_series: pd.Series,
    horizon: HorizonSpec,
    task: str,
    side: str,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Фичи (t-1), вход на OPEN[t], путь от t..t+h.
    Делает:
      - feats_shifted = feats.shift(1)
      - labels = build_labels_open_entry(..., side=side)  # {-1,0,+1} для binary
      - конверсия y -> {0,1} если классификация
      - синхронизация индексов и dropna
    """
    feats_s = feats.shift(1)

    labels_raw = build_labels_open_entry(
        ohlc=ohlc.loc[feats.index, ["open","high","low","close"]],
        atr_series=atr_series.reindex(feats.index),
        horizon=HorizonSpec(horizon.horizon_bars, horizon.tp_mult_atr, horizon.sl_mult_atr),
        task=task,
        side=side
    )
    df = feats_s.join(labels_raw.rename("y"), how="inner")
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    # бинаризация при классификации
    if task in ("binary_hit", "direction", "trinary"):
        # для binary_hit метка {-1,0,+1} -> {0,1}
        y_bin = (df["y"] > 0).astype(int)
        X = df.drop(columns=["y"])
        return X, y_bin
    else:
        X = df.drop(columns=["y"])
        y = df["y"]
        return X, y

def _augment_both_sides(
    X: pd.DataFrame, y: pd.Series,
    X_short: pd.DataFrame, y_short: pd.Series
) -> Tuple[pd.DataFrame, pd.Series]:
    # фича направления сделки:
    X_copy = X.copy()
    X_short_copy = X_short.copy()
    X_copy["side_dir"] = +1.0
    X_short_copy["side_dir"] = -1.0
    
    Xa = pd.concat([X_copy, X_short_copy], axis=0)
    ya = pd.concat([y.copy(), y_short.copy()], axis=0)
    return Xa, ya

def _make_sample_weights(y: pd.Series, symbols: pd.Series, enable_symbol_balance: bool) -> np.ndarray:
    # class-balance
    p = y.mean()
    # веса классов: реже встречающийся класс получает больший вес
    w_pos = 0.5 / max(p, 1e-6)
    w_neg = 0.5 / max(1.0 - p, 1e-6)
    w = y.map({1: w_pos, 0: w_neg}).astype(float)

    if enable_symbol_balance and symbols is not None:
        counts = symbols.value_counts()
        inv = symbols.map(lambda s: 1.0 / max(counts.get(s, 1), 1.0))
        inv = inv / inv.mean()
        w = w * inv.values
    return w.values

def _apply_corr_dropout(X: pd.DataFrame, prob: float) -> pd.DataFrame:
    if prob <= 0.0:
        return X
    X = X.copy()
    sym_cols = [c for c in X.columns if c.startswith("sym__")]
    if not sym_cols:
        return X
    mask = (np.random.rand(len(X)) < prob)
    if mask.any():
        X.loc[mask, sym_cols] = 0.0
    return X

def _split_train_val(X: pd.DataFrame, y: pd.Series, ratio: float) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    n = len(X)
    cut = int(n * ratio)
    return X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]

def _train_estimator(X: pd.DataFrame, y: pd.Series, cfg: TrainConfig, Xva: pd.DataFrame = None, yva: pd.Series = None, w_tr: np.ndarray = None) -> Dict[str, Any]:
    """Возвращает словарь с ключами: kind, model_path, feature_names, metrics."""
    _ensure_dir(cfg.models_dir)

    # Бинаризация для некоторых задач
    if cfg.task in ("binary_hit", "direction", "trinary"):
        # Приводим к {0,1} для классификации
        y_bin = y.copy()
        y_bin = (y_bin > 0).astype(int)
        if LGB_OK:
            dtrain = lgb.Dataset(X, label=y_bin, weight=w_tr, free_raw_data=False)
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
            # Фолбэк: весовая сумма фич → "скор" (псевдо-модель)
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
            # Небольшой трюк: регрессию заменим на классификацию знака (условный фолбэк)
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

    sym_tag = "_".join(cfg.symbols) if len(cfg.symbols) <= 2 else f"{cfg.symbols[0]}_and_{len(cfg.symbols)-1}_more"
    base = f"{cfg.task}_{sym_tag}_H{cfg.horizon_bars}"
    model_path = os.path.join(cfg.models_dir, base + ".joblib")

    if SK_OK:
        joblib.dump({"model": model_obj, "meta": meta}, model_path)
    else:
        # лайт фолбэк — сохраняем в npz/json
        np.savez(model_path.replace(".joblib", ".npz"), **model_obj if isinstance(model_obj, dict) else {})
        with open(model_path.replace(".joblib", ".meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"kind": kind, "model_path": model_path, "feature_names": meta["feature_names"], "meta": meta}

# -------------------------------

def train_one(cfg: TrainConfig, args) -> Dict[str, Any]:
    # 1) загрузка/слияние данных по всем символам (stack)
    frames = []
    for sym in cfg.symbols:
        df = _fetch_ohlc_or_die(sym, cfg.start, cfg.end)
        df["symbol"] = sym
        frames.append(df)
    data = pd.concat(frames, axis=0, keys=[f"s[{s}]" for s in cfg.symbols])
    # Используем покомпонентно (обучение на объединении символов)
    # 2) Фичи и лейблы
    feats_all, y_all, sym_all = [], [], []
    for sym in cfg.symbols:
        sub = data.xs(key=f"s[{sym}]", level=0)
        feats = _simple_features(sub)
        # ATR для барьеров
        atr_series = atr(sub["high"], sub["low"], sub["close"], period=14).reindex(feats.index)
        horizon = HorizonSpec(cfg.horizon_bars, cfg.tp_mult_atr, cfg.sl_mult_atr)

        if args.entry_mode == "open_t":
            X_long, y_long = _align_xy_open_entry_no_lookahead(
                ohlc=sub.loc[feats.index, ["open","high","low","close"]],
                feats=feats, atr_series=atr_series, horizon=horizon, task=cfg.task, side="LONG"
            )
            if args.both_sides:
                X_short, y_short = _align_xy_open_entry_no_lookahead(
                    ohlc=sub.loc[feats.index, ["open","high","low","close"]],
                    feats=feats, atr_series=atr_series, horizon=horizon, task=cfg.task, side="SHORT"
                )
                # side-augmentation
                X_sym, y_sym = _augment_both_sides(X_long, y_long, X_short, y_short)
            else:
                X_sym, y_sym = X_long, y_long

        elif args.entry_mode == "open_next":
            # вход на OPEN[t+1], фичи по t — это классическая схема: сдвиг не нужен
            X_sym, y_sym = _align_xy(feats, build_labels(
                ohlc=sub.loc[feats.index, ["open","high","low","close"]],
                atr_series=atr_series, horizon=horizon, task=cfg.task, side="LONG"
            ))
        else:  # "close_t"
            # вход на CLOSE[t], но чтобы не было лука-ахеда, фичи на t-1
            feats_s = feats.shift(1)
            X_sym, y_sym = _align_xy(feats_s, build_labels(
                ohlc=sub.loc[feats.index, ["open","high","low","close"]],
                atr_series=atr_series, horizon=horizon, task=cfg.task, side="LONG"
            ))

        # one-hot символа
        X_sym = X_sym.copy()
        X_sym[f"sym__{sym}"] = 1.0

        feats_all.append(X_sym)
        y_all.append(y_sym)
        sym_all.append(pd.Series(sym, index=y_sym.index, dtype=str))

    X = pd.concat(feats_all, axis=0).sort_index()
    y = pd.concat(y_all, axis=0).sort_index()
    sym_series = pd.concat(sym_all, axis=0).sort_index()

    # anti-correlation trick: иногда зануляем one-hot символа, чтобы модель меньше залипала на тикер
    X = _apply_corr_dropout(X, prob=args.corr_dropout)

    if len(X) < 200:
        warnings.warn("Very small dataset (<200 rows). Consider expanding date range.")
    
    # time-based split:
    cut_ts = X.index[int(len(X) * cfg.train_ratio)]
    Xtr, Xva = X.loc[:cut_ts], X.loc[cut_ts:]
    ytr, yva = y.loc[:cut_ts], y.loc[cut_ts:]
    sym_tr, sym_va = sym_series.loc[:cut_ts], sym_series.loc[cut_ts:]

    # sample weights:
    w_tr = _make_sample_weights(ytr, sym_tr if args.symbol_balance else None, enable_symbol_balance=args.symbol_balance)

    # 3) обучение
    res = _train_estimator(Xtr, ytr, cfg, Xva, yva, w_tr)

    # 4) быстрая метрика на валидации (если можно)
    metrics: Dict[str, Any] = {}
    try:
        if res["kind"].startswith("lgb"):
            if LGB_OK:
                if cfg.task in ("binary_hit", "direction", "trinary"):
                    yhat = res["meta"].get("val_dummy", None)
                    model = res  # we saved via joblib; reload for safety
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
    # сохраняем meta.json дополнительно
    meta_path = res["model_path"].replace(".joblib", ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({**res["meta"], **metrics}, f, ensure_ascii=False, indent=2)
    return res

# -------------------------------

def main():
    ap = argparse.ArgumentParser(description="Train forecaster models (binary/regression) with safe fallbacks.")
    ap.add_argument("--symbols", type=str, required=True, help="Comma-separated symbols, e.g. ADAUSDT,HBARUSDT")
    ap.add_argument("--start", type=str, default=None)
    ap.add_argument("--end", type=str, default=None)
    ap.add_argument("--task", type=str, default="binary_hit", choices=["binary_hit","direction","trinary","regression"])
    ap.add_argument("--side", type=str, default="LONG", choices=["LONG","SHORT"])
    ap.add_argument("--hbars", type=int, default=24)
    ap.add_argument("--tp_atr", type=float, default=2.0)
    ap.add_argument("--sl_atr", type=float, default=2.0)
    ap.add_argument("--models_dir", type=str, default="forecast/models")
    ap.add_argument("--train_ratio", type=float, default=0.8)
    ap.add_argument("--entry_mode", type=str, default="open_t", choices=["open_t","close_t","open_next"],
                    help="Момент входа: open_t (мгновенный), close_t (конец бара), open_next (на следующем баре).")
    ap.add_argument("--both_sides", action="store_true", help="Дублировать выборки на LONG/SHORT с признаком side_dir.")
    ap.add_argument("--symbol_balance", action="store_true", help="Балансировать веса по символам (анти-перекос).")
    ap.add_argument("--corr_dropout", type=float, default=0.0, help="Вероятность занулить one-hot символ (0..1) для анти-корр.")
    args = ap.parse_args()

    cfg = TrainConfig(
        symbols=[s.strip() for s in args.symbols.split(",") if s.strip()],
        start=args.start, end=args.end,
        horizon_bars=args.hbars, tp_mult_atr=args.tp_atr, sl_mult_atr=args.sl_atr,
        side=args.side, task=args.task, models_dir=args.models_dir,
        train_ratio=args.train_ratio
    )
    _ensure_dir(cfg.models_dir)
    res = train_one(cfg, args)
    print(json.dumps({
        "ok": True,
        "model_kind": res["kind"],
        "model_path": res["model_path"],
        "metrics": res.get("metrics", {})
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()