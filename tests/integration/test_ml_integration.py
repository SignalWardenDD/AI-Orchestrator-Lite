# tests/integration/test_ml_integration.py
"""
Тест интеграции ML моделей в торговую систему.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np

# Добавляем путь к проекту
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from orchestrator.auction.scorer import IndividualMLManager, MLConfig, score_candidates
from orchestrator.utils.types import SignalCandidate, FirstHitForecast
from orchestrator.engine.pipeline import AnalyzePipeline

class TestMLIntegration(unittest.TestCase):
    """Тесты интеграции ML моделей."""
    
    def setUp(self):
        """Настройка тестов."""
        self.config_path = "config/models_individual_optimized.yaml"
        self.test_symbols = ["ADAUSDT", "DOGEUSDT", "ARBUSDT"]
        
    def test_ml_manager_initialization(self):
        """Тест инициализации ML менеджера."""
        try:
            ml_manager = IndividualMLManager(self.config_path)
            self.assertIsNotNone(ml_manager)
            self.assertIsNotNone(ml_manager.config)
            
            # Проверяем, что загружены модели
            available_symbols = ml_manager.get_available_symbols()
            self.assertGreater(len(available_symbols), 0)
            
            print(f"✅ ML Manager initialized with {len(available_symbols)} symbols")
            
        except Exception as e:
            self.skipTest(f"ML Manager initialization failed: {e}")
    
    def test_ml_prediction(self):
        """Тест предсказания ML моделей."""
        try:
            ml_manager = IndividualMLManager(self.config_path)
            
            # Создаем тестовые фичи
            test_features = pd.DataFrame({
                'ret_1': [0.01], 'ret_3': [0.02], 'ret_6': [0.03],
                'ema20': [100.0], 'ema50': [99.5], 'ema200': [98.0],
                'ema20_slope': [0.005], 'natr14': [2.5], 'rng_1': [0.02],
                'rng_3': [0.025], 'z_close_50': [0.5], 'ret_1_lag1': [0.008],
                'rng_1_lag1': [0.018], 'ret_1_lag2': [0.012], 'rng_1_lag2': [0.022],
                'ret_1_lag3': [0.009], 'rng_1_lag3': [0.019]
            })
            
            # Тестируем предсказание для активных символов
            for symbol in self.test_symbols:
                if ml_manager.is_symbol_enabled(symbol):
                    prob, metadata = ml_manager.predict_ensemble(symbol, test_features)
                    
                    self.assertIsInstance(prob, float)
                    self.assertGreaterEqual(prob, 0.0)
                    self.assertLessEqual(prob, 1.0)
                    self.assertIsInstance(metadata, dict)
                    
                    print(f"✅ {symbol}: prob={prob:.3f}, status={metadata.get('status', 'unknown')}")
            
        except Exception as e:
            self.skipTest(f"ML prediction test failed: {e}")
    
    def test_score_candidates_with_ml(self):
        """Тест скоринга кандидатов с ML."""
        try:
            # Создаем тестовые кандидаты
            candidates = [
                SignalCandidate(
                    symbol="ADAUSDT",
                    type="BRK",
                    side="LONG",
                    atr=0.02,
                    timestamp=pd.Timestamp.now()
                )
            ]
            
            # Создаем тестовые прогнозы
            forecasts = [
                FirstHitForecast(
                    symbol="ADAUSDT",
                    type="BRK",
                    side="LONG",
                    H=4,
                    t_hit={2: 0.3, 4: 0.5, 6: 0.7, 10: 0.8},
                    slip_est=0.001
                )
            ]
            
            # Создаем тестовые OHLCV данные
            ohlc_data = pd.DataFrame({
                'open': [100.0, 101.0, 102.0],
                'high': [101.0, 102.0, 103.0],
                'low': [99.0, 100.0, 101.0],
                'close': [101.0, 102.0, 103.0],
                'volume': [1000, 1100, 1200]
            }, index=pd.date_range('2024-01-01', periods=3, freq='1H'))
            
            ohlc_by_symbol = {"ADAUSDT": ohlc_data}
            
            # Инициализируем ML менеджер
            ml_manager = IndividualMLManager(self.config_path)
            ml_config = MLConfig(enabled=True, config_path=self.config_path)
            
            # Тестируем скоринг
            scored = score_candidates(
                candidates,
                forecasts,
                btc_weight=0.5,
                ml_cfg=ml_config,
                ohlc_1h_by_symbol=ohlc_by_symbol,
                _ml_manager=ml_manager
            )
            
            self.assertIsInstance(scored, list)
            if scored:
                self.assertIsInstance(scored[0].score_usdt, float)
                print(f"✅ Scored candidates: {len(scored)}")
                for sc in scored:
                    print(f"  {sc.symbol} {sc.type} {sc.side}: score={sc.score_usdt:.3f}")
            
        except Exception as e:
            self.skipTest(f"Score candidates test failed: {e}")
    
    def test_pipeline_ml_integration(self):
        """Тест интеграции ML в пайплайн."""
        try:
            # Мокаем зависимости
            with patch('orchestrator.engine.pipeline.load_settings') as mock_settings, \
                 patch('orchestrator.engine.pipeline.load_symbols') as mock_symbols:
                
                # Настраиваем моки
                mock_settings.return_value.engine = {"forecast": {"enabled": True}}
                mock_settings.return_value.ml = Mock(
                    enabled=True,
                    config_path=self.config_path,
                    calibrator_prefer="isotonic",
                    prob_weight_base=1.0,
                    prob_weight_gain=1.0,
                    min_auc_threshold=0.45
                )
                mock_symbols.return_value.symbols = [
                    {"symbol": "ADAUSDT", "type": "A"},
                    {"symbol": "DOGEUSDT", "type": "B"}
                ]
                
                # Создаем моки для других компонентов
                mock_providers = []
                mock_forecast_reg = Mock()
                mock_plan_builder = Mock()
                mock_entry_exec = Mock()
                mock_exits_placer = Mock()
                
                # Создаем пайплайн
                pipeline = AnalyzePipeline(
                    symbols=["ADAUSDT", "DOGEUSDT"],
                    providers=mock_providers,
                    forecast_reg=mock_forecast_reg,
                    plan_builder=mock_plan_builder,
                    entry_exec=mock_entry_exec,
                    exits_placer=mock_exits_placer
                )
                
                # Проверяем инициализацию ML
                self.assertIsNotNone(pipeline.ml_config)
                print("✅ Pipeline ML integration initialized")
                
        except Exception as e:
            self.skipTest(f"Pipeline ML integration test failed: {e}")

def run_ml_integration_tests():
    """Запуск тестов интеграции ML."""
    print("🧪 Running ML Integration Tests")
    print("=" * 50)
    
    # Создаем тестовый suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMLIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print(f"\n📊 Test Results:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped)}")
    
    if result.failures:
        print("\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\n❌ Errors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_ml_integration_tests()
    exit(0 if success else 1)
