from __future__ import annotations
from .exec.broker import Broker
from .forecast.registry import ForecastRegistry
from .signals.breakout import BreakoutProvider
from .signals.pullback_mr import PullbackMRProvider
from .signals.trend import TrendProvider
from .signals.bollinger_play import BollingerPlayProvider
from .telemetry.storage import CSVStore
from .telemetry.reports import Reports
from .telemetry.logger import setup_logging
from .utils.env import load_env
from .state.store import StateStore

class Container:
    def __init__(self):
        env = load_env()
        setup_logging(env.log_dir)
        self.store = StateStore()
        self.broker = Broker(env.binance_key, env.binance_secret, env.base_url)
        self.forecasts = ForecastRegistry()
        # По умолчанию A‑группа; при инициализации на символ можно подставить свою
        self.providers = [
            BreakoutProvider(group="A"),
            PullbackMRProvider(),
            TrendProvider(),
            BollingerPlayProvider(),
        ]
        self.csv = CSVStore("./data")
        self.reports = Reports(self.csv)
