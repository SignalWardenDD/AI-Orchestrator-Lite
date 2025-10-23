# orchestrator/exec/reconciler.py
"""
Модуль сверки ордеров и позиций с Binance.
Идемпотентная сверка с защитой от ухудшения SL/TP.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from .order_tags import parse_role_from_cid, ROLE_ENTRY, ROLE_SL, ROLE_TP1, ROLE_TP2

def _price_diff_pct(a: float, b: float) -> float:
    """Вычисляет разность цен в процентах."""
    return abs(a - b) / max(1e-12, b) * 100.0

def desired_orders_for_symbol(tracker, symbol: str) -> Dict[str, dict]:
    """
    Формирует 'желаемый' набор ордеров по ролям: ENTRY (если ещё не заполнен), SL, TP1, TP2.
    Возвращает словарь role -> {'price','qty','side'}.
    """
    desired: Dict[str, dict] = {}
    
    # ENTRY (если есть ожидающий)
    ent = tracker.pending_entries.get(symbol)
    if ent:
        desired[ROLE_ENTRY] = {
            "price": ent.entry_limit, 
            "qty": ent.qty, 
            "side": ent.side
        }

    # SL
    sl = tracker.stops.get(symbol)
    if sl:
        desired[ROLE_SL] = {
            "price": sl.entry_limit, 
            "qty": sl.qty, 
            "side": sl.side
        }

    # TP
    tps = tracker.take_profits.get(symbol, [])
    if len(tps) >= 1:
        desired[ROLE_TP1] = {
            "price": tps[0].entry_limit, 
            "qty": tps[0].qty, 
            "side": tps[0].side
        }
    if len(tps) >= 2:
        desired[ROLE_TP2] = {
            "price": tps[1].entry_limit, 
            "qty": tps[1].qty, 
            "side": tps[1].side
        }
    
    return desired

def live_orders_by_role(broker, symbol: str) -> Dict[str, dict]:
    """
    Читает open orders с биржи и мапит по роли из clientOrderId.
    """
    out: Dict[str, dict] = {}
    try:
        for o in broker.list_open_orders(symbol=symbol):
            role = parse_role_from_cid(o.get("clientOrderId"))
            if role:
                out[role] = {
                    "orderId": o["orderId"],
                    "price": float(o["price"]),
                    "qty": float(o["origQty"]),
                    "side": o["side"].upper(),
                }
    except Exception as e:
        print(f"⚠️  Ошибка получения ордеров для {symbol}: {e}")
    
    return out

def reconcile_symbol(cfg, broker, tracker, symbol: str) -> dict:
    """
    Идемпотентная сверка:
      - удаляем только лишние ордера (есть на бирже, нет в желаемом)
      - создаём недостающие (есть в желаемом, нет на бирже)
      - корректируем МИНИМАЛЬНО, учитывая hysteresis_pct и respect_improvements
    Возвращает краткий отчёт.
    """
    try:
        hys = float(cfg.reconciliation.hysteresis_pct)
        respect = bool(cfg.reconciliation.respect_improvements)

        desired = desired_orders_for_symbol(tracker, symbol)
        live = live_orders_by_role(broker, symbol)

        to_cancel: List[dict] = []
        to_create: List[Tuple[str, dict]] = []   # (role, spec)
        to_replace: List[Tuple[str, dict, dict]] = []  # (role, live, desired)

        # 1) удалить лишние (есть live, нет desired)
        for role, l in live.items():
            if role not in desired:
                to_cancel.append({
                    "symbol": symbol, 
                    "orderId": l["orderId"], 
                    "role": role
                })

        # 2) создать недостающие
        for role, d in desired.items():
            if role not in live:
                to_create.append((role, d))
            else:
                # 3) проверить расхождение цены/qty
                l = live[role]
                price_gap = _price_diff_pct(d["price"], l["price"])
                qty_gap = abs(d["qty"] - l["qty"]) > 1e-12
                need_replace = price_gap > hys or qty_gap

                if role == ROLE_SL and respect:
                    # не ухудшаем SL: для LONG — не опускать ниже текущего, для SHORT — не поднимать выше
                    if d["side"] == "SELL":  # это SL для LONG
                        # улучшение: d.price > l.price
                        if d["price"] <= l["price"]:
                            need_replace = False  # не ухудшаем
                    else:  # BUY SL для SHORT
                        if d["price"] >= l["price"]:
                            need_replace = False

                if need_replace:
                    to_replace.append((role, l, d))

        # 4) применить лимиты батча
        maxC = int(cfg.reconciliation.max_batch_cancel)
        maxN = int(cfg.reconciliation.max_batch_create)
        cancel_apply = to_cancel[:maxC]
        create_apply = to_create[:maxN]

        # 5) выполнить: отмены
        for it in cancel_apply:
            try:
                broker.cancel_order(symbol=it["symbol"], order_id=it["orderId"])
            except Exception as e:
                print(f"⚠️  Ошибка отмены ордера {it['orderId']}: {e}")

        # 6) заменить (отмена+создание)
        for role, l, d in to_replace[:maxC]:
            try:
                broker.cancel_order(symbol=symbol, order_id=l["orderId"])
                if role == ROLE_ENTRY:
                    broker.place_postonly_limit(symbol, d["side"], d["qty"], d["price"], ttl=8, role=ROLE_ENTRY)
                elif role == ROLE_SL:
                    broker.place_reduce_only_stop(symbol, d["side"], d["qty"], d["price"], role=ROLE_SL)
                elif role in (ROLE_TP1, ROLE_TP2):
                    broker.place_reduce_only(symbol, d["side"], d["qty"], d["price"], kind="TP", role=role)
            except Exception as e:
                print(f"⚠️  Ошибка замены ордера {role}: {e}")

        # 7) дозавести недостающие
        for role, d in create_apply:
            try:
                if role == ROLE_ENTRY:
                    broker.place_postonly_limit(symbol, d["side"], d["qty"], d["price"], ttl=8, role=ROLE_ENTRY)
                elif role == ROLE_SL:
                    broker.place_reduce_only_stop(symbol, d["side"], d["qty"], d["price"], role=ROLE_SL)
                elif role in (ROLE_TP1, ROLE_TP2):
                    broker.place_reduce_only(symbol, d["side"], d["qty"], d["price"], kind="TP", role=role)
            except Exception as e:
                print(f"⚠️  Ошибка создания ордера {role}: {e}")

        return {
            "canceled": len(cancel_apply),
            "created": len(create_apply) + len(to_replace[:maxC]),
            "replaced": len(to_replace[:maxC]),
            "skipped_cancel": max(0, len(to_cancel) - len(cancel_apply)),
            "skipped_create": max(0, len(to_create) - len(create_apply)),
        }
        
    except Exception as e:
        return {"error": str(e)}
