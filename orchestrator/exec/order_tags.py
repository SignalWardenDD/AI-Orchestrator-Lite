# orchestrator/exec/order_tags.py
"""
Маркировка ролей ордеров для безопасной синхронизации.
Позволяет однозначно сопоставлять ордера по «роли», а не по внутренним id.
"""

from __future__ import annotations
from typing import Optional

# Роли ордеров
ROLE_ENTRY = "ENTRY"
ROLE_SL    = "SL"
ROLE_TP1   = "TP1"
ROLE_TP2   = "TP2"

# Префикс для clientOrderId
CID_PREFIX = "SWL"   # SignalWarden Lite
# clientOrderId: SWL:<SYMBOL>:<ROLE>:<unixms>

def make_cid(symbol: str, role: str, now_ms: int) -> str:
    """
    Создает уникальный clientOrderId для ордера.
    
    Args:
        symbol: Символ торговой пары
        role: Роль ордера (ENTRY, SL, TP1, TP2)
        now_ms: Текущее время в миллисекундах
    
    Returns:
        clientOrderId в формате SWL:<SYMBOL>:<ROLE>:<unixms>
    """
    return f"{CID_PREFIX}:{symbol}:{role}:{now_ms}"

def parse_role_from_cid(client_order_id: Optional[str]) -> Optional[str]:
    """
    Извлекает роль ордера из clientOrderId.
    
    Args:
        client_order_id: clientOrderId с биржи
    
    Returns:
        Роль ордера или None если не удалось распарсить
    """
    if not client_order_id:
        return None
    try:
        parts = client_order_id.split(":")
        if len(parts) >= 3 and parts[0] == CID_PREFIX:
            return parts[2]
    except Exception:
        pass
    return None

def is_our_order(client_order_id: Optional[str]) -> bool:
    """
    Проверяет, является ли ордер нашим (созданным нашей системой).
    
    Args:
        client_order_id: clientOrderId с биржи
    
    Returns:
        True если ордер создан нашей системой
    """
    if not client_order_id:
        return False
    return client_order_id.startswith(f"{CID_PREFIX}:")
