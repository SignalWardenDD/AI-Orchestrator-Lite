from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class EnvCfg:
    binance_key: str | None
    binance_secret: str | None
    base_url: str | None
    log_dir: str


def load_env() -> EnvCfg:
    # Загружаем .env файл
    load_dotenv()
    
    return EnvCfg(
        binance_key=os.getenv("BINANCE_KEY"),
        binance_secret=os.getenv("BINANCE_SECRET"),
        base_url=os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com"),
        log_dir=os.getenv("LOG_DIR", "./logs")
    )
