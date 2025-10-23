from __future__ import annotations
from typing import Dict

# Восстановление состояния: подтягиваем открытые позиции и гарантируем SL/TP‑ордера

def reconcile_from_exchange(store, broker) -> None:
    # Для каждого символа, у которого позиция ≠ 0, восстановить запись
    # Пример: берём все позиции из API (в реале фильтруй под торгуемые символы)
    # Здесь ожидается, что broker.position_info(symbol) вернёт dict с ключами: entryPrice, positionAmt, unrealizedProfit
    # Внимание: знаковость qty определяет side
    restored = 0
    for sym in list(store.positions.keys()):
        # очистим старые фантомы: рефреш делаем заново
        store.positions.pop(sym, None)

    # Этот список символов можно получить из конфигов/DI; здесь короткий пример
    symbols = ["ADAUSDT", "LTCUSDT", "DOGEUSDT"]
    for sym in symbols:
        info = broker.position_info(sym)
        amt = float(info.get("positionAmt", 0) or 0)
        if abs(amt) < 1e-9:
            continue
        entry = float(info.get("entryPrice", 0) or 0)
        side = "LONG" if amt > 0 else "SHORT"
        from .store import Position
        store.apply_fill_open(Position(symbol=sym, side=side, qty_init=abs(amt), qty=abs(amt), entry_price=entry, ts_open=0))
        restored += 1
    # В реальной версии тут же можно сверить reduce‑only SL/TP и выставить при необходимости.
