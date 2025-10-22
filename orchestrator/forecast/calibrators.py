# forecast/calibrators.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss
    import joblib
    SK_OK = True
except Exception:  # scikit-learn may be absent in bare NoML env
    SK_OK = False


CalibType = Literal["platt", "isotonic"]


def _ece(probs: np.ndarray, y_true: np.ndarray, bins: int = 10) -> float:
    """
    Expected Calibration Error (ECE), simple equal-width binning over [0,1].
    """
    if probs.size == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        mask = (probs >= edges[i]) & (probs < edges[i+1] if i < bins - 1 else probs <= edges[i+1])
        if not np.any(mask):
            continue
        p_bin = probs[mask].mean()
        y_bin = y_true[mask].mean()
        w = mask.mean()
        ece += w * abs(p_bin - y_bin)
    return float(ece)


@dataclass
class Calibrator:
    """
    Thin wrapper to keep a unified interface for Platt (logistic) or Isotonic.
    """
    kind: CalibType = "platt"
    model: Any = None

    def fit(self, raw_scores: np.ndarray, y_true: np.ndarray):
        if not SK_OK:
            # no-op calibrator in NoML environment
            self.kind = "noop"
            self.model = None
            return self

        raw_scores = raw_scores.reshape(-1, 1)
        y = y_true.astype(int)

        if self.kind == "platt":
            lr = LogisticRegression(max_iter=200)
            lr.fit(raw_scores, y)
            self.model = lr
        elif self.kind == "isotonic":
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.model = iso.fit(raw_scores.ravel(), y)
        else:
            raise ValueError(f"Unknown calibrator kind: {self.kind}")
        return self

    def predict_proba(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Returns calibrated probabilities in [0,1].
        """
        if self.model is None:
            # noop: map scores to (0,1) via sigmoid-ish normalization
            x = np.asarray(raw_scores, dtype=float)
            # affine to 0..1 with guard
            mn, mx = np.nanmin(x), np.nanmax(x)
            if not np.isfinite(mn) or not np.isfinite(mx) or abs(mx - mn) < 1e-9:
                return np.full_like(x, 0.5, dtype=float)
            return (x - mn) / (mx - mn)

        if self.kind == "platt":
            return self.model.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
        elif self.kind == "isotonic":
            return self.model.predict(raw_scores.ravel())
        else:
            # should not happen
            x = np.asarray(raw_scores, dtype=float)
            return np.clip(x, 0.0, 1.0)

    def save(self, path: str) -> None:
        if not SK_OK:
            return
        joblib.dump({"kind": self.kind, "model": self.model}, path)

    @staticmethod
    def load(path: str) -> "Calibrator":
        if not SK_OK:
            return Calibrator(kind="noop", model=None)
        obj = joblib.load(path)
        return Calibrator(kind=obj["kind"], model=obj["model"])


def calibration_report(raw_scores: np.ndarray, y_true: np.ndarray, kind: CalibType = "platt", bins: int = 10) -> Dict[str, float]:
    """
    Fit calibrator and return simple metrics: Brier/ECE before/after.
    """
    raw = np.asarray(raw_scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    raw01 = (raw - raw.min()) / (raw.max() - raw.min() + 1e-12)

    brier_before = float(brier_score_loss(y, raw01)) if SK_OK else np.nan
    ece_before = _ece(raw01, y, bins=bins)

    calib = Calibrator(kind=kind).fit(raw, y)
    prob = calib.predict_proba(raw)

    brier_after = float(brier_score_loss(y, prob)) if SK_OK else np.nan
    ece_after = _ece(prob, y, bins=bins)

    return {
        "brier_before": brier_before,
        "brier_after": brier_after,
        "ece_before": ece_before,
        "ece_after": ece_after,
    }