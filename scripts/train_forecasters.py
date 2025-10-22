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
from utils.mathx import natr, atr, ewma, zscore, pct_change_safe, EPS
from forecast.labeling import HorizonSpec, build_labels
# Data fetchers — если у тебя другие имена, эти try/except сделают фолбэк
try:
    from data.ingest import fetch_ohlcv_1h as fetch_ohlcv
except Exception:
    fetch_ohlcv = None

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
    if fetch_ohlcv is None:
        raise RuntimeError("data.ingest.fetch_ohlcv_1h not found. Please implement or wire your fetcher.")
    df = fetch_ohlcv(symbol, start=start, end=end)
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

def _split_train_val(X: pd.DataFrame, y: pd.Series, ratio: float) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    n = len(X)
    cut = int(n * ratio)
    return X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]

def _train_estimator(X: pd.DataFrame, y: pd.Series, cfg: TrainConfig) -> Dict[str, Any]:
    """Возвращает словарь с ключами: kind, model_path, feature_names, metrics."""
    _ensure_dir(cfg.models_dir)

    # Бинаризация для некоторых задач
    if cfg.task in ("binary_hit", "direction", "trinary"):
        # Приводим к {0,1} для классификации
        y_bin = y.copy()
        y_bin = (y_bin > 0).astype(int)
        if LGB_OK:
            dtrain = lgb.Dataset(X, label=y_bin)
            params = {
                "objective": "binary",
                "metric": ["auc", "binary_logloss"],
                "learning_rate": 0.05,
                "num_leaves": 31,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 1,
                "seed": cfg.random_state
            }
            model = lgb.train(params, dtrain, num_boost_round=300)
            kind = "lgb_binary"
            model_obj = model
        elif SK_OK:
            pipe = Pipeline(steps=[
                ("scaler", StandardScaler(with_mean=False)),
                ("lr", LogisticRegression(max_iter=500, random_state=cfg.random_state))
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

def train_one(cfg: TrainConfig) -> Dict[str, Any]:
    # 1) загрузка/слияние данных по всем символам (stack)
    frames = []
    for sym in cfg.symbols:
        df = _fetch_ohlc_or_die(sym, cfg.start, cfg.end)
        df["symbol"] = sym
        frames.append(df)
    data = pd.concat(frames, axis=0, keys=[f"s[{s}]" for s in cfg.symbols])
    # Используем покомпонентно (обучение на объединении символов)
    # 2) Фичи и лейблы
    feats_all, y_all = [], []
    for sym in cfg.symbols:
        sub = data.xs(key=f"s[{sym}]", level=0)
        feats = _simple_features(sub)
        # ATR для барьеров
        atr_series = atr(sub["high"], sub["low"], sub["close"], period=14).reindex(feats.index)
        horizon = HorizonSpec(cfg.horizon_bars, cfg.tp_mult_atr, cfg.sl_mult_atr)
        labels = build_labels(
            ohlc=sub.loc[feats.index, ["open","high","low","close"]],
            atr_series=atr_series,
            horizon=horizon,
            task=cfg.task,
            side=cfg.side
        )
        X, y = _align_xy(feats, labels)
        # символ как категориальная фича (one-hot)
        X = X.copy()
        X[f"sym__{sym}"] = 1.0
        feats_all.append(X)
        y_all.append(y)

    X = pd.concat(feats_all, axis=0).sort_index()
    y = pd.concat(y_all, axis=0).sort_index()

    if len(X) < 200:
        warnings.warn("Very small dataset (<200 rows). Consider expanding date range.")
    Xtr, Xva, ytr, yva = _split_train_val(X, y, cfg.train_ratio)

    # 3) обучение
    res = _train_estimator(Xtr, ytr, cfg)

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
    args = ap.parse_args()

    cfg = TrainConfig(
        symbols=[s.strip() for s in args.symbols.split(",") if s.strip()],
        start=args.start, end=args.end,
        horizon_bars=args.hbars, tp_mult_atr=args.tp_atr, sl_mult_atr=args.sl_atr,
        side=args.side, task=args.task, models_dir=args.models_dir,
        train_ratio=args.train_ratio
    )
    _ensure_dir(cfg.models_dir)
    res = train_one(cfg)
    print(json.dumps({
        "ok": True,
        "model_kind": res["kind"],
        "model_path": res["model_path"],
        "metrics": res.get("metrics", {})
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()