# orchestrator/forecast/calibration.py
"""
Функции калибровки для per-signal моделей.
"""

import numpy as np
from sklearn.isotonic import IsotonicRegression

def fit_isotonic(raw_scores: np.ndarray, y_true: np.ndarray) -> IsotonicRegression:
    """
    Обучает изотоника калибратор на сырых скорах и истинных метках.
    
    Args:
        raw_scores: Сырые скоры модели (вероятности)
        y_true: Истинные метки (0/1)
        
    Returns:
        Обученный изотоника калибратор
    """
    return IsotonicRegression(out_of_bounds="clip").fit(raw_scores, y_true)
