# integration_examples.py
"""
Примеры интеграции новых модулей в существующие пайплайны системы.
Эти примеры показывают, как безопасно подключить новые модули без изменения существующего кода.
"""

from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any

# Импорты новых модулей
from orchestrator.utils.mathx import natr, rolling_corr, sigmoid, zscore
from orchestrator.risk.filters import CalmMarketGuard, SpikeGuard, CorrBlocker
from orchestrator.forecast.labeling import build_labels, HorizonSpec
from orchestrator.forecast.calibrators import Calibrator, calibration_report

# Импорты существующих модулей
from orchestrator.utils.types import SignalCandidate
from orchestrator.guards.common import edge_guard
from orchestrator.auction.scorer import score_candidates


def enhanced_risk_filtering_example():
    """
    Пример интеграции новых риск-фильтров в существующий пайплайн.
    Показывает, как добавить дополнительные проверки без изменения существующего кода.
    """
    
    # Создаем экземпляры новых фильтров
    calm_guard = CalmMarketGuard(threshold_pct=0.8, lookback=14)
    spike_guard = SpikeGuard(window=24, spike_mult=4.0)
    corr_blocker = CorrBlocker(window=48, max_corr=0.95)
    
    def enhanced_candidate_filtering(candidates: List[SignalCandidate], 
                                   ohlc_data: Dict[str, pd.DataFrame],
                                   btc_data: pd.DataFrame) -> List[SignalCandidate]:
        """
        Расширенная фильтрация кандидатов с новыми риск-фильтрами.
        """
        filtered_candidates = []
        
        for candidate in candidates:
            symbol = candidate.symbol
            
            # 1. Существующая фильтрация (edge_guard)
            guard_decision, meta = edge_guard(candidate)
            if guard_decision.name == "REJECT":
                continue
                
            # 2. Новые фильтры
            if symbol in ohlc_data:
                ohlc = ohlc_data[symbol]
                
                # Проверка спокойного рынка
                allowed, reason, _ = calm_guard.check(ohlc)
                if not allowed:
                    print(f"Filtered {symbol}: {reason}")
                    continue
                
                # Проверка на спайки
                allowed, reason, _ = spike_guard.check(ohlc['close'])
                if not allowed:
                    print(f"Filtered {symbol}: {reason}")
                    continue
                
                # Проверка корреляции с BTC
                if not btc_data.empty:
                    allowed, reason, _ = corr_blocker.check(
                        ohlc['close'], btc_data['close']
                    )
                    if not allowed:
                        print(f"Filtered {symbol}: {reason}")
                        continue
            
            filtered_candidates.append(candidate)
            
        return filtered_candidates


def enhanced_scoring_with_mathx_example():
    """
    Пример использования новых математических функций в скоринге.
    Показывает, как улучшить расчеты без изменения существующего кода.
    """
    
    def enhanced_score_calculation(candidates: List[SignalCandidate], 
                                  forecasts: List, 
                                  btc_weight: float,
                                  ohlc_data: Dict[str, pd.DataFrame]) -> List:
        """
        Улучшенный расчет скора с использованием новых математических функций.
        """
        # Используем существующую функцию скоринга
        scored = score_candidates(candidates, forecasts, btc_weight)
        
        # Дополнительные улучшения с новыми функциями
        enhanced_scores = []
        
        for scored_candidate in scored:
            symbol = scored_candidate.symbol
            
            # Дополнительные метрики из mathx
            if symbol in ohlc_data:
                ohlc = ohlc_data[symbol]
                
                # Рассчитываем NATR для дополнительной информации
                natr_series = natr(ohlc['high'], ohlc['low'], ohlc['close'])
                current_natr = natr_series.iloc[-1]
                
                # Z-score для волатильности
                vol_zscore = zscore(natr_series, window=20)
                vol_z = vol_zscore.iloc[-1] if not vol_zscore.empty else 0.0
                
                # Применяем дополнительные поправки к скору
                volatility_adjustment = sigmoid(vol_z)  # 0-1 нормализация
                
                # Модифицируем скор с учетом волатильности
                enhanced_score = scored_candidate.score_usdt * (0.8 + 0.2 * volatility_adjustment)
                
                # Обновляем скор
                scored_candidate.score_usdt = enhanced_score
                scored_candidate.components.update({
                    'natr': current_natr,
                    'vol_zscore': vol_z,
                    'vol_adjustment': volatility_adjustment
                })
            
            enhanced_scores.append(scored_candidate)
            
        return enhanced_scores


def ml_training_integration_example():
    """
    Пример интеграции новых модулей для ML обучения.
    Показывает, как использовать labeling и calibrators в тренировочных скриптах.
    """
    
    def prepare_training_data(ohlc_data: pd.DataFrame, 
                            atr_series: pd.Series,
                            symbol: str,
                            side: str) -> Dict[str, Any]:
        """
        Подготовка данных для обучения с использованием новых модулей.
        """
        
        # Создаем спецификацию горизонта
        horizon_spec = HorizonSpec(
            horizon_bars=24,  # 24 часа
            tp_mult_atr=2.0,  # TP на 2 ATR
            sl_mult_atr=2.0   # SL на 2 ATR
        )
        
        # Создаем лейблы для разных задач
        labels_binary = build_labels(
            ohlc_data, atr_series, horizon_spec, 
            task="binary_hit", side=side
        )
        
        labels_direction = build_labels(
            ohlc_data, atr_series, horizon_spec,
            task="direction", side=side
        )
        
        labels_regression = build_labels(
            ohlc_data, atr_series, horizon_spec,
            task="regression", side=side
        )
        
        return {
            'symbol': symbol,
            'side': side,
            'labels_binary': labels_binary,
            'labels_direction': labels_direction,
            'labels_regression': labels_regression,
            'horizon_spec': horizon_spec
        }
    
    def calibrate_model_predictions(raw_scores: pd.Series, 
                                  true_labels: pd.Series,
                                  calibration_type: str = "platt") -> Dict[str, Any]:
        """
        Калибровка предсказаний модели.
        """
        
        # Создаем калибратор
        calibrator = Calibrator(kind=calibration_type)
        
        # Обучаем калибратор
        calibrator.fit(raw_scores.values, true_labels.values)
        
        # Получаем калиброванные вероятности
        calibrated_probs = calibrator.predict_proba(raw_scores.values)
        
        # Генерируем отчет о калибровке
        report = calibration_report(
            raw_scores.values, 
            true_labels.values, 
            kind=calibration_type
        )
        
        return {
            'calibrator': calibrator,
            'calibrated_probs': calibrated_probs,
            'calibration_report': report
        }


def enhanced_feature_engineering_example():
    """
    Пример использования новых математических функций для создания признаков.
    """
    
    def create_enhanced_features(ohlc_data: pd.DataFrame) -> pd.DataFrame:
        """
        Создание расширенных признаков с использованием mathx.
        """
        features = ohlc_data.copy()
        
        # Базовые признаки
        features['returns'] = ohlc_data['close'].pct_change()
        features['volatility'] = features['returns'].rolling(20).std()
        
        # Новые признаки с mathx
        features['natr'] = natr(ohlc_data['high'], ohlc_data['low'], ohlc_data['close'])
        features['natr_zscore'] = zscore(features['natr'], window=20)
        features['natr_sigmoid'] = sigmoid(features['natr_zscore'])
        
        # EWMA для сглаживания
        features['close_ewma'] = features['close'].ewm(span=20).mean()
        features['vol_ewma'] = features['volatility'].ewm(span=20).mean()
        
        # Корреляция с предыдущими значениями
        features['autocorr'] = rolling_corr(
            features['returns'], 
            features['returns'].shift(1), 
            window=20
        )
        
        return features


if __name__ == "__main__":
    print("Примеры интеграции новых модулей:")
    print("1. enhanced_risk_filtering_example() - расширенная фильтрация рисков")
    print("2. enhanced_scoring_with_mathx_example() - улучшенный скоринг")
    print("3. ml_training_integration_example() - интеграция для ML")
    print("4. enhanced_feature_engineering_example() - создание признаков")
