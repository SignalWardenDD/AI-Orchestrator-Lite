from __future__ import annotations
import logging

log = logging.getLogger("audit")


def audit_line(**fields):
    # одна строка JSON‑подобная
    try:
        msg = " | ".join([f"{k}={v}" for k,v in fields.items()])
    except Exception:
        msg = str(fields)
    log.info(msg)
