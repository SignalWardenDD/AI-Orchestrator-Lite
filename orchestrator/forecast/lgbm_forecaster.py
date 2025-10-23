# forecast/lgbm_forecaster.py
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

# Опциональные зависимости
try:
    import joblib
    SK_OK = True
except Exception:
    SK_OK = False

try:
    import lightgbm as lgb  # noqa: F401
    LGB_OK = True
except Exception:
    LGB_OK = False

from orchestrator.forecast.calibrators import Calibrator


@dataclass
class LoadedModel:
    kind: str
    model: Any
    feature_names: List[str]
    meta: Dict[str, Any]
    calibrator: Optional[Calibrator] = None


class Forecaster:
    """
    Унифицированный загрузчик/предсказатель:
    - Поддерживает модели, сохранённые train_forecasters.py (.joblib)
    - Автоподхват калибратора рядом ( *.calib.platt.joblib / *.calib.isotonic.joblib ), если есть
    - Возвращает calibrated proba [0..1] через predict_proba_df / predict_proba_row
    - Безопасен к отсутствию sklearn/lightgbm (использует фолбэк-модель/нормализацию)
    """

    def __init__(self, model_path: str, calibrator_prefer: Optional[str] = None):
        """
        model_path: путь к *.joblib от scripts/train_forecasters.py
        calibrator_prefer: "platt" | "isotonic" | None (если None — авто: isotonic > platt)
        """
        self.model_path = model_path
        self.loaded: Optional[LoadedModel] = None
        self._load(calibrator_prefer=calibrator_prefer)

    # ---------- Public API ----------

    def predict_proba_row(self, features_row: Dict[str, float]) -> float:
        """
        Предикт для одного кандидата (словарь фич -> значение).
        Вернёт probability (0..1). При ошибке вернёт 0.5.
        """
        try:
            X = self._row_to_df(features_row)
            proba = self.predict_proba_df(X)
            return float(proba.iloc[0])
        except Exception:
            return 0.5

    def predict_proba_df(self, X: pd.DataFrame) -> pd.Series:
        """
        Предикт для батча фич (DataFrame). Возвращает pd.Series prob[0..1].
        Отсутствующие фичи будут автоматически добавлены нулями, лишние — отброшены.
        """
        if self.loaded is None:
            return pd.Series(np.full(len(X), 0.5), index=X.index)

        Xp = self._prepare_X(X, self.loaded.feature_names)
        raw = self._predict_raw(self.loaded, Xp)
        prob = self._calibrate_if_needed(raw, self.loaded.calibrator)
        # защита от NaN/inf
        prob = np.nan_to_num(prob, nan=0.5, posinf=1.0, neginf=0.0)
        return pd.Series(np.clip(prob, 0.0, 1.0), index=Xp.index)

    def get_feature_names(self) -> List[str]:
        return list(self.loaded.feature_names) if self.loaded else []

    def meta(self) -> Dict[str, Any]:
        return dict(self.loaded.meta) if self.loaded else {}

    # ---------- Internal ----------

    def _load(self, calibrator_prefer: Optional[str]) -> None:
        if not SK_OK:
            # Без joblib не можем загрузить полноценные модели; оставим пустую конфигурацию.
            self.loaded = LoadedModel(
                kind="noop",
                model=None,
                feature_names=[],
                meta={"note": "joblib not available; using noop forecaster"},
                calibrator=None,
            )
            return

        obj = joblib.load(self.model_path)  # {"model": ..., "meta": {...}}
        model = obj["model"]
        meta = obj.get("meta", {})
        kind = meta.get("kind", "sk_logreg")
        feature_names = meta.get("feature_names", [])

        calib = self._try_load_calibrator(self.model_path, prefer=calibrator_prefer)
        self.loaded = LoadedModel(kind=kind, model=model, feature_names=feature_names, meta=meta, calibrator=calib)

    @staticmethod
    def _try_load_calibrator(model_path: str, prefer: Optional[str]) -> Optional[Calibrator]:
        """
        Ищет рядом файлы:
          *.calib.isotonic.joblib
          *.calib.platt.joblib
        Приоритет: prefer, иначе isotonic > platt.
        """
        base = os.path.splitext(model_path)[0]
        paths = {
            "isotonic": base + ".calib.isotonic.joblib",
            "platt": base + ".calib.platt.joblib",
        }

        order: List[str]
        if prefer in ("isotonic", "platt"):
            order = [prefer, "isotonic" if prefer == "platt" else "platt"]
        else:
            order = ["isotonic", "platt"]

        if not SK_OK:
            return None

        for k in order:
            p = paths[k]
            if os.path.exists(p):
                try:
                    obj = joblib.load(p)
                    # Объект сохранялся через Calibrator.save(joblib.dump({...}))
                    # На всякий случай поддержим 2 формата: сам Calibrator или словарь
                    if isinstance(obj, Calibrator):
                        return obj
                    # Старый формат — словарь: {"kind": "...", "model": ...}
                    if isinstance(obj, dict) and "kind" in obj and "model" in obj:
                        return Calibrator(kind=obj["kind"], model=obj["model"])
                except Exception:
                    continue
        return None

    @staticmethod
    def _prepare_X(X: pd.DataFrame, required: List[str]) -> pd.DataFrame:
        X = X.copy()
        # Добавляем отсутствующие фичи нулями
        for c in required:
            if c not in X.columns:
                X[c] = 0.0
        # Оставляем только нужные
        X = X[required]
        # Ограждаем бесконечности/NaN
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return X

    @staticmethod
    def _row_to_df(features_row: Dict[str, float]) -> pd.DataFrame:
        return pd.DataFrame([features_row])

    @staticmethod
    def _predict_raw(loaded: LoadedModel, Xp: pd.DataFrame) -> np.ndarray:
        """
        Возвращает «сырые» предсказания модели:
          - для binary моделей — скоры/вероятности (ещё не калиброванные)
          - для линейного фолбэка — [0..1] нормировка веса*фичи
        """
        kind = loaded.kind
        model = loaded.model

        # LightGBM booster
        if kind.startswith("lgb"):
            if hasattr(model, "predict"):
                raw = model.predict(Xp)
                return np.asarray(raw, dtype=float)
            # safety:
            s = Xp.values @ np.zeros((Xp.shape[1],))
            return (s - s.min()) / (s.max() - s.min() + 1e-12)

        # sklearn pipelines (логрег и т.п.)
        if kind.startswith("sk_"):
            if hasattr(model, "predict_proba"):
                pp = model.predict_proba(Xp)[:, 1]
                return np.asarray(pp, dtype=float)
            if hasattr(model, "decision_function"):
                df = model.decision_function(Xp)
                # приведём к 0..1
                mn, mx = np.nanmin(df), np.nanmax(df)
                if not np.isfinite(mn) or not np.isfinite(mx) or abs(mx - mn) < 1e-9:
                    return np.full(len(Xp), 0.5, dtype=float)
                return (df - mn) / (mx - mn)

        # «линейный» фолбэк без sklearn/lgbm
        if kind.startswith("linear_fallback"):
            if isinstance(model, dict) and "weights" in model:
                names = model.get("feature_names", list(Xp.columns))
                if set(names).issubset(set(Xp.columns)):
                    X1 = Xp[names].values
                else:
                    X1 = Xp.values
                w = np.asarray(model["weights"], dtype=float)
                w = w[: X1.shape[1]] if w.shape[0] >= X1.shape[1] else np.pad(w, (0, X1.shape[1]-w.shape[0]))
                s = X1 @ w
                mn, mx = np.nanmin(s), np.nanmax(s)
                if not np.isfinite(mn) or not np.isfinite(mx) or abs(mx - mn) < 1e-12:
                    return np.full(len(Xp), 0.5, dtype=float)
                return (s - mn) / (mx - mn + 1e-12)

        # неизвестный тип — вернём 0.5
        return np.full(len(Xp), 0.5, dtype=float)

    @staticmethod
    def _calibrate_if_needed(raw: np.ndarray, calibrator: Optional[Calibrator]) -> np.ndarray:
        if calibrator is None:
            # клипнем на всякий случай
            return np.clip(raw, 0.0, 1.0)
        try:
            p = calibrator.predict_proba(raw.astype(float))
            return np.clip(p, 0.0, 1.0)
        except Exception:
            return np.clip(raw, 0.0, 1.0)