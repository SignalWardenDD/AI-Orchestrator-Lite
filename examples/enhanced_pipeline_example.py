# enhanced_pipeline_example.py
"""
Пример расширенного пайплайна с интеграцией новых модулей.
Показывает, как безопасно добавить новые функции без изменения существующего кода.
"""

from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd

# Импорты существующих модулей
from orchestrator.engine.pipeline import AnalyzePipeline
from orchestrator.utils.types import SignalCandidate
from orchestrator.guards.common import edge_guard
from orchestrator.guards.conversions import to_retest, to_mr_inversion, to_trend_from_pb
from orchestrator.telemetry.audit import audit_line

# Импорты новых модулей
from orchestrator.risk.filters import CalmMarketGuard, SpikeGuard, CorrBlocker
from orchestrator.utils.mathx import natr, rolling_corr, zscore, sigmoid


class EnhancedAnalyzePipeline(AnalyzePipeline):
    """
    Расширенный пайплайн с интеграцией новых модулей.
    Наследует от существующего AnalyzePipeline и добавляет новые функции.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Инициализируем новые фильтры
        self.calm_guard = CalmMarketGuard(threshold_pct=0.8, lookback=14)
        self.spike_guard = SpikeGuard(window=24, spike_mult=4.0)
        self.corr_blocker = CorrBlocker(window=48, max_corr=0.95)
        
        # Кэш для OHLC данных
        self._ohlc_cache: Dict[str, pd.DataFrame] = {}
        self._btc_data: pd.DataFrame = None
    
    def _get_ohlc_data(self, symbol: str) -> pd.DataFrame:
        """Получение OHLC данных с кэшированием."""
        if symbol not in self._ohlc_cache:
            from ..data.ingest import fetch_ohlcv_1h
            bars = fetch_ohlcv_1h(symbol, limit=220)
            from ..data.features import build_feature_rows
            frows = build_feature_rows(bars)
            
            # Конвертируем в DataFrame для удобства
            df = pd.DataFrame(frows)
            self._ohlc_cache[symbol] = df
        
        return self._ohlc_cache[symbol]
    
    def _get_btc_data(self) -> pd.DataFrame:
        """Получение BTC данных с кэшированием."""
        if self._btc_data is None:
            from ..data.ingest import fetch_ohlcv_1h
            bars = fetch_ohlcv_1h("BTCUSDT", limit=220)
            from ..data.features import build_feature_rows
            frows = build_feature_rows(bars)
            self._btc_data = pd.DataFrame(frows)
        
        return self._btc_data
    
    def _enhanced_risk_filtering(self, candidate: SignalCandidate) -> tuple[bool, str, Dict]:
        """
        Расширенная фильтрация рисков с использованием новых модулей.
        Возвращает (allowed, reason, metadata)
        """
        symbol = candidate.symbol
        
        try:
            # Получаем OHLC данные
            ohlc_data = self._get_ohlc_data(symbol)
            
            # 1. Проверка спокойного рынка
            allowed, reason, meta = self.calm_guard.check(ohlc_data)
            if not allowed:
                return False, f"CALM_FILTER: {reason}", meta
            
            # 2. Проверка на спайки
            allowed, reason, meta = self.spike_guard.check(ohlc_data['close'])
            if not allowed:
                return False, f"SPIKE_FILTER: {reason}", meta
            
            # 3. Проверка корреляции с BTC
            btc_data = self._get_btc_data()
            if not btc_data.empty:
                allowed, reason, meta = self.corr_blocker.check(
                    ohlc_data['close'], btc_data['close']
                )
                if not allowed:
                    return False, f"CORR_FILTER: {reason}", meta
            
            return True, "PASSED", {}
            
        except Exception as e:
            audit_line(event="enhanced_filter_error", symbol=symbol, error=str(e))
            return True, "ERROR_FALLBACK", {}  # В случае ошибки пропускаем
    
    def _collect_candidates(self, symbol: str) -> List[SignalCandidate]:
        """
        Переопределяем метод сбора кандидатов для добавления новых фильтров.
        """
        if self.store and symbol in self.store.paused_symbols:
            return []
        if self.store and not self.store.get_slot_free(symbol):
            return []
        
        bars = self._fetch_ohlcv_1h(symbol, limit=220)
        frows = self._build_feature_rows(bars)
        cands: List[SignalCandidate] = []
        
        for p in self.providers:
            try:
                cands.extend(p.generate(symbol, frows))
            except Exception as e:
                audit_line(event="provider_error", symbol=symbol, provider=getattr(p, "type_name", "?"), err=str(e))
        
        # Существующая фильтрация (edge + конверсии)
        filtered: List[SignalCandidate] = []
        for c in cands:
            gd, meta = edge_guard(c)
            if gd.name == "REJECT":
                audit_line(event="guard_reject", symbol=c.symbol, type=c.type, side=c.side, reason=str(meta))
                continue
            if gd.name == "ADAPT":
                # упрощённая конверсия: сначала retest, если указан экстрем
                if c.meta.get("retest_only", 0.0) > 0:
                    c = to_retest(c)
                elif c.type == "PB" and c.meta.get("hook", 0.0) == 0.0:
                    c = to_trend_from_pb(c)
                else:
                    c = to_mr_inversion(c)
            
            # НОВАЯ ФИЛЬТРАЦИЯ: расширенные риск-фильтры
            allowed, reason, filter_meta = self._enhanced_risk_filtering(c)
            if not allowed:
                audit_line(
                    event="enhanced_filter_reject", 
                    symbol=c.symbol, 
                    type=c.type, 
                    side=c.side, 
                    reason=reason,
                    metadata=filter_meta
                )
                continue
            
            # Добавляем метаданные фильтрации к кандидату
            c.meta.update(filter_meta)
            filtered.append(c)
        
        return filtered
    
    def _enhanced_scoring(self, candidates: List[SignalCandidate], forecasts: List, btc_weight: float) -> List:
        """
        Расширенный скоринг с использованием новых математических функций.
        """
        from ..auction.scorer import score_candidates
        
        # Используем существующую функцию скоринга
        scored = score_candidates(candidates, forecasts, btc_weight)
        
        # Дополнительные улучшения с новыми функциями
        enhanced_scores = []
        
        for scored_candidate in scored:
            symbol = scored_candidate.symbol
            
            try:
                # Получаем OHLC данные для дополнительных расчетов
                ohlc_data = self._get_ohlc_data(symbol)
                
                # Рассчитываем дополнительные метрики
                natr_series = natr(ohlc_data['high'], ohlc_data['low'], ohlc_data['close'])
                current_natr = natr_series.iloc[-1]
                
                # Z-score для волатильности
                vol_zscore = zscore(natr_series, window=20)
                vol_z = vol_zscore.iloc[-1] if not vol_zscore.empty else 0.0
                
                # Применяем дополнительные поправки к скору
                volatility_adjustment = sigmoid(vol_z)  # 0-1 нормализация
                
                # Модифицируем скор с учетом волатильности (мягкая поправка)
                volatility_factor = 0.9 + 0.2 * volatility_adjustment  # 0.9-1.1 диапазон
                enhanced_score = scored_candidate.score_usdt * volatility_factor
                
                # Обновляем скор
                scored_candidate.score_usdt = enhanced_score
                scored_candidate.components.update({
                    'natr': current_natr,
                    'vol_zscore': vol_z,
                    'vol_adjustment': volatility_adjustment,
                    'volatility_factor': volatility_factor
                })
                
                audit_line(
                    event="enhanced_scoring", 
                    symbol=symbol,
                    original_score=scored_candidate.score_usdt / volatility_factor,
                    enhanced_score=enhanced_score,
                    volatility_factor=volatility_factor
                )
                
            except Exception as e:
                audit_line(event="enhanced_scoring_error", symbol=symbol, error=str(e))
                # В случае ошибки используем оригинальный скор
            
            enhanced_scores.append(scored_candidate)
        
        return enhanced_scores
    
    def run_once(self):
        """
        Переопределяем основной метод с добавлением расширенных функций.
        """
        all_cands: List[SignalCandidate] = []
        for s in self.symbols:
            all_cands.extend(self._collect_candidates(s))
        
        if not all_cands:
            return
        
        horizons = [2,4,6,10]
        if bool(self.settings.get("forecast", {}).get("enabled", True)):
            forecasts = self.forecast_reg.forecast(all_cands, horizons)
        else:
            forecasts = self.no_ml.predict_many(all_cands, horizons)
        
        from ..data.ingest import fetch_btc_context
        btc_weight = fetch_btc_context().get("btc_weight", 0.5)
        
        # Используем расширенный скоринг
        scored = self._enhanced_scoring(all_cands, forecasts, btc_weight)
        
        from ..auction.selector import pick_winner
        winner = pick_winner(scored)
        
        if not winner:
            return
        
        # Остальная логика остается без изменений
        from ..data.ingest import fetch_ohlcv_1h
        from ..data.features import build_feature_rows
        from ..guards.realtime_recheck import realtime_recheck
        
        bars_1h = fetch_ohlcv_1h(winner.symbol, limit=30)
        f1h = build_feature_rows(bars_1h)
        recent_1h = [{"ema20": r.get("ema20",0.0), "rsi2": r.get("rsi2",50.0), "close": r.get("close",0.0)} for r in f1h[-3:]]
        
        rr = realtime_recheck(
            candidate=next(c for c in all_cands if c.symbol==winner.symbol and c.type==winner.type and c.side==winner.side),
            recent_15m=[],
            recent_1h=recent_1h,
        )
        
        if rr.decision == "cancel":
            audit_line(event="recheck_cancel_pre", symbol=winner.symbol, reason=rr.reason)
            return
        
        # Build plan -> LIMIT & track
        last_price = self.entry_exec.broker.fetch_price(winner.symbol)
        spec = self._sym_spec.get(winner.symbol, {"step_size": 0.001, "tick_size": 0.0001})
        step_size = float(spec.get("step_size", 0.001))
        tick_size = float(spec.get("tick_size", 0.0001))
        cand = next(c for c in all_cands if (c.symbol == winner.symbol and c.type == winner.type and c.side == winner.side))
        plan = self.plan_builder.build(cand, last_price=last_price, step_size=step_size, tick_size=tick_size)
        order_id = self.entry_exec.place_limit_and_track(plan)
        
        if order_id:
            if self.store:
                from ..state.store import Position
                self.store.apply_fill_open(Position(symbol=plan.symbol, side=plan.side, qty_init=plan.qty, qty=plan.qty, entry_price=plan.entry_limit, ts_open=0))
            audit_line(event="limit_placed", symbol=plan.symbol, side=plan.side, order_id=order_id, price=plan.entry_limit, qty=plan.qty, pre_recheck=rr.decision)


# Пример использования расширенного пайплайна
def create_enhanced_pipeline(symbols, providers, forecast_reg, plan_builder, entry_exec, exits_placer, store=None):
    """
    Фабричная функция для создания расширенного пайплайна.
    """
    return EnhancedAnalyzePipeline(
        symbols=symbols,
        providers=providers,
        forecast_reg=forecast_reg,
        plan_builder=plan_builder,
        entry_exec=entry_exec,
        exits_placer=exits_placer,
        store=store
    )
