# orchestrator/signals/types.py
"""
Единая точка правды для имён типов сигналов.
"""

# Типы сигналов
SIGNAL_TYPES = ("BRK", "PB", "MR", "BB")  # Breakout, Pullback, Mean-Reversion, Bollinger

# Горизонты по умолчанию
DEFAULT_HORIZONS = ("H12", "H24")

# Маппинг типов сигналов на провайдеры
SIGNAL_TO_PROVIDER = {
    "BRK": "BreakoutProvider",
    "PB": "PullbackMRProvider", 
    "MR": "PullbackMRProvider",
    "BB": "BollingerPlayProvider"
}
