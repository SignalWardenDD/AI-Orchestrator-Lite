from __future__ import annotations
import logging, os
from logging.handlers import RotatingFileHandler

_DEF_FMT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(log_dir: str = "./logs", level: int = logging.INFO) -> None:
    os.makedirs(log_dir, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(_DEF_FMT))
    root.addHandler(ch)

    fh = RotatingFileHandler(os.path.join(log_dir, "orchestrator.log"), maxBytes=5_000_000, backupCount=3)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(_DEF_FMT))
    root.addHandler(fh)

    audit = logging.getLogger("audit")
    ah = RotatingFileHandler(os.path.join(log_dir, "audit.log"), maxBytes=10_000_000, backupCount=5)
    ah.setLevel(level)
    ah.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    audit.addHandler(ah)

def setup_logger(name: str):
    """Настраивает логгер."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
