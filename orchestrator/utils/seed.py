# orchestrator/utils/seed.py
"""
Утилиты для установки seed для воспроизводимости.
"""

import random
import numpy as np

def set_seed(seed: int = 42):
    """Устанавливает seed для всех генераторов случайных чисел."""
    random.seed(seed)
    np.random.seed(seed)
    
    # Для LightGBM
    try:
        import lightgbm as lgb
        # LightGBM не имеет set_seed, используем параметр random_state в модели
        pass
    except ImportError:
        pass
    
    # Для sklearn
    try:
        from sklearn.utils import check_random_state
        check_random_state(seed)
    except ImportError:
        pass
