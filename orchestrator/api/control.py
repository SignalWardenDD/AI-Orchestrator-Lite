from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(prefix="/control")

_STORE = None

def attach_store(store):
    global _STORE
    _STORE = store

@router.post("/pause/{symbol}")
async def pause_symbol(symbol: str):
    if _STORE is None:
        return {"ok": False, "error": "store_not_attached"}
    _STORE.paused_symbols.add(symbol.upper())
    return {"ok": True, "symbol": symbol.upper(), "paused": True}

@router.post("/resume/{symbol}")
async def resume_symbol(symbol: str):
    if _STORE is None:
        return {"ok": False, "error": "store_not_attached"}
    _STORE.paused_symbols.discard(symbol.upper())
    return {"ok": True, "symbol": symbol.upper(), "paused": False}

def get_status():
    """Возвращает статус системы."""
    return {"system": "running", "timestamp": "2024-01-01T00:00:00Z"}

def get_positions():
    """Возвращает активные позиции."""
    return []
