# orchestrator/utils/io.py
"""
Утилиты для работы с файловой системой.
"""

import os
from pathlib import Path
from typing import Union

def ensure_dir(path: Union[str, Path]) -> Path:
    """Создает директорию если она не существует."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
