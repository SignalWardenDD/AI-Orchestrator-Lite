from __future__ import annotations
import asyncio
from .wiring import Container
from .utils.timebars import periodic
from .engine.pipeline import AnalyzePipeline
from .exec.planner import PlanBuilder
from .exec.entry import EntryExecutor
from .exec.exits import ExitsPlacer
from .exec.order_tracker import OrderTracker
from .exec.sl_manager import SLManager
from .telemetry.audit import audit_line
from .telemetry import metrics as METRICS
from .api import control as CTL
from .data import ingest as data_ingest
from .risk.limits import DailyLossGuard, WeeklySoftLimiter
from .state import recon as RECON
from config.loader import load_settings, load_risk, load_ladders, load_symbols

ANALYZE_SEC = 120
ORDERCHECK_SEC = 15
TPSL_SEC = 2

class App:
    def __init__(self):
        self.di = Container()
        data_ingest.set_data_source(self.di.broker)
        s = load_settings(); r = load_risk(); l = load_ladders(); sy = load_symbols()
        self.order_tracker = OrderTracker()
        self.entry = EntryExecutor(self.di.broker, slippage_cap_pct=float(s.engine.get("slippage_cap_pct", 0.12)), order_tracker=self.order_tracker)
        self.exits = ExitsPlacer(self.di.broker)
        self.slmgr = SLManager(self.di.broker)
        symbols = [x.get("symbol") for x in sy.symbols] or ["ADAUSDT"]
        pb = PlanBuilder(
            fixed_notional_usdt=float(r.position.get("fixed_notional_usdt", 15.0)),
            sl_mult_map=r.sl_multipliers,
            tp_ladder=l.tp,
            be_usdt=l.be,
            slippage_cap_pct=float(s.engine.get("slippage_cap_pct", 0.12)),
            ttl_min=int(s.engine.get("postonly_ttl_sec_min", 8)),
            ttl_max=int(s.engine.get("postonly_ttl_sec_max", 12)),
        )
        self.pipeline = AnalyzePipeline(symbols, self.di.providers, self.di.forecasts, pb, self.entry, self.exits, store=self.di.store)
        # Метрики и /control
        METRICS.set_state_store(self.di.store)
        METRICS.set_order_tracker(self.order_tracker)
        CTL.attach_store(self.di.store)
        # Лимиты риска
        self.daily_guard = DailyLossGuard(limit_usdt=float(r.limits.get("daily_loss_usdt", -7.5)))
        self.weekly = WeeklySoftLimiter(max_neg_days=int(r.limits.get("weekly_max_neg_days", 3)))
        # Реконсиляция на старте
        try:
            RECON.reconcile_from_exchange(self.di.store, self.di.broker)
        except Exception as e:
            audit_line(event="recon_error", err=str(e))

    async def analyze_cycle(self):
        try:
            # Лимит дня: если пробит — не строим новые входы
            if not self.daily_guard.allowed(self.di.store.day_realized_usdt):
                audit_line(event="daily_limit_hit", realized=self.di.store.day_realized_usdt)
                return
            # Недельный soft‑лимит: если >=3 отрицательных дня — паузим «спайковые» пары
            if self.weekly.should_pause_spiky(__import__("datetime").date.today()):
                for s in list(self.di.store.paused_symbols) + []:
                    pass  # уже в паузах
            self.pipeline.run_once()
        except Exception as e:
            audit_line(event="analyze_error", err=str(e))

    async def ordercheck_cycle(self):
        try:
            expired = self.order_tracker.expired()
            if not expired:
                return
            for t in expired:
                # 1) отменяем лимит
                try:
                    self.di.broker.cancel_order(t.symbol, t.order_id)
                except Exception as e:
                    audit_line(event="cancel_fail", symbol=t.symbol, order_id=t.order_id, err=str(e))
                # 2) быстрый re-check на последних барах
                bars_1h = fetch_ohlcv_1h(t.symbol, limit=30)
                f1h = build_feature_rows(bars_1h)
                recent_1h = [
                    {"ema20": r.get("ema20", 0.0), "rsi2": r.get("rsi2", 50.0), "close": r.get("close", 0.0)}
                    for r in f1h[-3:]
                ]
                # 15m можно добавить аналогично при необходимости
                rr = realtime_recheck(
                    candidate=type("TmpC", (), {
                        "symbol": t.symbol, "side": t.side, "entry_price": t.entry_limit, "atr": max(1e-9, t.atr), "ema20": t.ema20, "meta": {}
                    })(),
                    recent_15m=[],
                    recent_1h=recent_1h,
                )
                # 3) решение: valid -> market fallback (если slippage ок), adapt/cancel -> пропуск
                px = self.di.broker.fetch_price(t.symbol)
                slip_pct = abs(px - t.entry_limit) / max(t.entry_limit, 1e-9) * 100
                if rr.decision == "valid" and slip_pct <= float(0.12):
                    side = "BUY" if t.side == "LONG" else "SELL"
                    try:
                        self.di.broker.place_market(t.symbol, side, t.qty)
                        audit_line(event="market_fallback", symbol=t.symbol, qty=t.qty, price=px, slip_pct=round(slip_pct,4))
                    except Exception as e:
                        audit_line(event="market_fail", symbol=t.symbol, err=str(e))
                else:
                    audit_line(event="ttl_recheck", symbol=t.symbol, decision=rr.decision, reason=rr.reason, slippage=round(slip_pct,4))
                # 4) удалить из трекера
                self.order_tracker.pop(t.order_id)
        except Exception as e:
            audit_line(event="ordercheck_error", err=str(e))

    async def tpsl_cycle(self):
        """Трекинг частичных TP по факту уменьшения позиции и перенос SL в денежный BE/подъём.
        Простая эвристика: сравниваем текущий размер позиции с qty_init и отмечаем TP1/TP2/TP3 по порогам лесенки.
        """
        try:
            for sym, pos in list(self.di.store.positions.items()):
                # Узнаём фактический текущий размер позиции по бирже
                info = self.di.broker.position_info(sym)
                amt = abs(float(info.get("positionAmt", 0) or 0))
                if amt <= 1e-9:
                    # позиция закрыта (по TP/SL/ручному) — убираем из стора
                    self.di.store.apply_close(sym, realized_usdt=0.0)
                    audit_line(event="position_closed", symbol=sym)
                    continue
                # Обновим qty в store
                self.di.store.update_qty(sym, amt)
                # Пороги лесенки (по спецификации): 20/25/25/30
                q0 = pos.qty_init
                tp1_lvl = q0 * (1 - 0.20 + 1e-6)
                tp2_lvl = q0 * (1 - 0.20 - 0.25 + 1e-6)
                tp3_lvl = q0 * (1 - 0.20 - 0.25 - 0.25 + 1e-6)
                # Денежные уровни BE
                if not pos.tp1_done and amt <= tp1_lvl:
                    new_sl = self.slmgr.move_to_be(sym, pos.side, pos.entry_price, be_usdt=0.15, total_qty=amt)
                    pos.tp1_done = True
                    audit_line(event="sl_to_be_after_tp1", symbol=sym, new_sl=new_sl)
                if not pos.tp2_done and amt <= tp2_lvl:
                    new_sl = self.slmgr.raise_after_tp(sym, pos.side, pos.entry_price, add_usdt=0.35, total_qty=amt)
                    pos.tp2_done = True
                    audit_line(event="sl_raise_after_tp2", symbol=sym, new_sl=new_sl)
                if not pos.tp3_done and amt <= tp3_lvl:
                    new_sl = self.slmgr.raise_after_tp(sym, pos.side, pos.entry_price, add_usdt=0.80, total_qty=amt)
                    pos.tp3_done = True
                    audit_line(event="sl_raise_after_tp3", symbol=sym, new_sl=new_sl)
        except Exception as e:
            audit_line(event="tpsl_error", err=str(e))

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(periodic(ANALYZE_SEC, self.analyze_cycle))
        loop.create_task(periodic(ORDERCHECK_SEC, self.ordercheck_cycle))
        loop.create_task(periodic(TPSL_SEC, self.tpsl_cycle))
        loop.run_forever()


def main():
    App().run()

if __name__ == "__main__":
    main()
