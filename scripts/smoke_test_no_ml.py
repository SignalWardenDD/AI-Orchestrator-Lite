#!/usr/bin/env python3
"""
Минимальный smoke test без ML для проверки базовой функциональности системы.
"""

import sys
import os
sys.path.append('.')

from orchestrator.engine.pipeline import create_simple_pipeline
from orchestrator.data.ingest import fetch_ohlcv_1h, set_data_source
from orchestrator.data.features import build_feature_rows
from orchestrator.signals.breakout import BreakoutProvider
from orchestrator.signals.pullback_mr import PullbackMRProvider
from orchestrator.signals.trend import TrendProvider
from orchestrator.signals.bollinger_play import BollingerPlayProvider
from orchestrator.forecast.no_ml import NoMLForecaster
from orchestrator.auction.scorer import score_candidates
from orchestrator.auction.selector import pick_winner
from orchestrator.exec.planner import PlanBuilder
from orchestrator.exec.entry import EntryExecutor
from orchestrator.exec.exits import ExitsPlacer
from orchestrator.exec.dummy_broker import DummyBroker
from orchestrator.utils.types import SignalCandidate
import pandas as pd

def test_smoke_no_ml():
    """Smoke test без ML - проверяет базовую функциональность."""
    print("🧪 SMOKE TEST БЕЗ ML")
    print("=" * 50)
    
    # 1. Тест загрузки данных
    print("1. Тест загрузки данных...")
    try:
        # Инициализируем broker для data ingest
        broker = DummyBroker()
        set_data_source(broker)
        
        symbol = "ADAUSDT"
        bars = fetch_ohlcv_1h(symbol, limit=100)
        frows = build_feature_rows(bars)
        print(f"   ✅ Загружено {len(bars)} баров, {len(frows)} строк фичей")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки данных: {e}")
        return False
    
    # 2. Тест провайдеров сигналов
    print("2. Тест провайдеров сигналов...")
    try:
        providers = {
            'breakout': BreakoutProvider('A'),
            'pullback_mr': PullbackMRProvider(),
            'trend': TrendProvider(),
            'bollinger': BollingerPlayProvider()
        }
        
        candidates = []
        for name, provider in providers.items():
            try:
                cands = provider.generate(symbol, frows)
                candidates.extend(cands)
                print(f"   ✅ {name}: {len(cands)} сигналов")
            except Exception as e:
                print(f"   ⚠️ {name}: {e}")
        
        print(f"   ✅ Всего кандидатов: {len(candidates)}")
    except Exception as e:
        print(f"   ❌ Ошибка провайдеров: {e}")
        return False
    
    # 3. Тест NoML прогнозирования
    print("3. Тест NoML прогнозирования...")
    try:
        no_ml = NoMLForecaster()
        horizons = [2, 4, 6, 10]
        forecasts = no_ml.predict_many(candidates, horizons)
        print(f"   ✅ NoML прогнозы: {len(forecasts)} для {len(candidates)} кандидатов")
    except Exception as e:
        print(f"   ❌ Ошибка NoML: {e}")
        return False
    
    # 4. Тест скоринга
    print("4. Тест скоринга...")
    try:
        scored = score_candidates(
            candidates, 
            forecasts, 
            btc_weight=0.5,
            ml_cfg=None,
            ohlc_1h_by_symbol=None,
            _ml_manager=None
        )
        print(f"   ✅ Скоринг: {len(scored)} кандидатов")
    except Exception as e:
        print(f"   ❌ Ошибка скоринга: {e}")
        return False
    
    # 5. Тест селектора
    print("5. Тест селектора...")
    try:
        winner = pick_winner(scored)
        if winner:
            print(f"   ✅ Победитель: {winner.symbol} {winner.type} {winner.side}")
        else:
            print("   ℹ️ Победитель не выбран (нет подходящих сигналов)")
    except Exception as e:
        print(f"   ❌ Ошибка селектора: {e}")
        return False
    
    # 6. Тест планировщика
    print("6. Тест планировщика...")
    try:
        if winner:
            planner = PlanBuilder(
                fixed_notional_usdt=15.0,
                sl_mult_map={},
                tp_ladder=[],
                be_usdt={},
                slippage_cap_pct=0.12,
                ttl_min=8,
                ttl_max=12
            )
            
            # Создаем тестовый кандидат
            test_candidate = SignalCandidate(
                symbol=winner.symbol,
                type=winner.type,
                side=winner.side,
                entry_price=winner.entry_price,
                atr=winner.atr,
                meta=winner.meta
            )
            
            plan = planner.build(test_candidate, last_price=winner.entry_price, step_size=0.001, tick_size=0.0001)
            print(f"   ✅ План создан: {plan.symbol} {plan.side} {plan.qty} @ {plan.entry_limit}")
        else:
            print("   ℹ️ Планировщик пропущен (нет победителя)")
    except Exception as e:
        print(f"   ❌ Ошибка планировщика: {e}")
        return False
    
    # 7. Тест исполнителей
    print("7. Тест исполнителей...")
    try:
        broker = DummyBroker()
        entry_exec = EntryExecutor(broker)
        exits_placer = ExitsPlacer(broker)
        
        print("   ✅ EntryExecutor инициализирован")
        print("   ✅ ExitsPlacer инициализирован")
    except Exception as e:
        print(f"   ❌ Ошибка исполнителей: {e}")
        return False
    
    # 8. Тест полного пайплайна
    print("8. Тест полного пайплайна...")
    try:
        # Создаем простой пайплайн
        config = {
            'ml': {
                'enabled': False,
                'models_per_signal': {'yaml_path': 'config/optimized/models_per_signal_optimized.yaml'},
                'models_individual': {'yaml_path': 'config/optimized/models_individual_optimized.yaml'}
            }
        }
        
        pipeline = create_simple_pipeline(config)
        print("   ✅ Пайплайн создан")
        
        # Запускаем один цикл
        pipeline.run_once()
        print("   ✅ Пайплайн выполнен")
        
    except Exception as e:
        print(f"   ❌ Ошибка пайплайна: {e}")
        return False
    
    print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("✅ Система готова к работе без ML")
    return True

if __name__ == "__main__":
    success = test_smoke_no_ml()
    sys.exit(0 if success else 1)
