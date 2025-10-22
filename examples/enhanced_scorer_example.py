# enhanced_scorer_example.py
"""
Пример интеграции ML скорера в существующий auction/scorer.py.
Показывает, как безопасно добавить ML функциональность без изменения существующего кода.
"""

from __future__ import annotations
from typing import Dict, List
import pandas as pd

# Импорты существующих модулей
from orchestrator.utils.types import SignalCandidate, FirstHitForecast, ScoredCandidate
from orchestrator.auction.scorer import score_candidates as original_score_candidates

# Импорты новых модулей
from orchestrator.auction.ml_scorer import enhance_score_with_ml, get_ml_scorer


def enhanced_score_candidates(cands: List[SignalCandidate], forecasts: List[FirstHitForecast], btc_weight: float, ohlc_data: Dict[str, pd.DataFrame] = None) -> List[ScoredCandidate]:
    """
    Расширенная версия score_candidates с поддержкой ML моделей.
    
    Args:
        cands: Кандидаты сигналов
        forecasts: Прогнозы
        btc_weight: BTC вес
        ohlc_data: OHLC данные по символам (опционально)
    
    Returns:
        Список скорированных кандидатов
    """
    # Используем оригинальную функцию скоринга
    scored = original_score_candidates(cands, forecasts, btc_weight)
    
    # Получаем ML скорер
    ml_scorer = get_ml_scorer()
    
    # Улучшаем скоры с помощью ML моделей
    enhanced_scored = []
    
    for scored_candidate in scored:
        try:
            # Получаем OHLC данные для символа
            symbol_ohlc = ohlc_data.get(scored_candidate.symbol) if ohlc_data else None
            
            # Улучшаем скор с ML
            enhanced_score = ml_scorer.enhance_score_with_ml(
                candidate=SignalCandidate(
                    symbol=scored_candidate.symbol,
                    type=scored_candidate.type,
                    side=scored_candidate.side,
                    entry_price=0.0,  # Не используется в ML
                    atr=0.0,  # Не используется в ML
                    ema20=0.0,  # Не используется в ML
                    meta={},
                    ts=0
                ),
                base_score=scored_candidate.score_usdt,
                horizon=scored_candidate.H_best,
                ohlc_data=symbol_ohlc
            )
            
            # Создаем улучшенный кандидат
            enhanced_candidate = ScoredCandidate(
                symbol=scored_candidate.symbol,
                type=scored_candidate.type,
                side=scored_candidate.side,
                H_best=scored_candidate.H_best,
                score_usdt=enhanced_score,
                components={
                    **scored_candidate.components,
                    'ml_enhanced': True,
                    'ml_factor': enhanced_score / max(scored_candidate.score_usdt, 1e-9)
                }
            )
            
            enhanced_scored.append(enhanced_candidate)
            
        except Exception as e:
            # В случае ошибки используем оригинальный скор
            print(f"⚠️  Ошибка ML улучшения для {scored_candidate.symbol}: {e}")
            enhanced_scored.append(scored_candidate)
    
    return enhanced_scored


def safe_enhanced_score_candidates(cands: List[SignalCandidate], forecasts: List[FirstHitForecast], btc_weight: float, ohlc_data: Dict[str, pd.DataFrame] = None) -> List[ScoredCandidate]:
    """
    Безопасная версия enhanced_score_candidates с fallback на оригинальную функцию.
    """
    try:
        # Проверяем доступность ML моделей
        ml_scorer = get_ml_scorer()
        if not ml_scorer.forecasters:
            print("ℹ️  ML модели недоступны, используем оригинальный скоринг")
            return original_score_candidates(cands, forecasts, btc_weight)
        
        return enhanced_score_candidates(cands, forecasts, btc_weight, ohlc_data)
        
    except Exception as e:
        print(f"⚠️  Ошибка ML скоринга, используем оригинальный: {e}")
        return original_score_candidates(cands, forecasts, btc_weight)


# Пример интеграции в AnalyzePipeline
class EnhancedAnalyzePipeline:
    """
    Пример расширенного пайплайна с ML скорингом.
    Показывает, как интегрировать ML функциональность.
    """
    
    def __init__(self, *args, **kwargs):
        # Инициализация оригинального пайплайна
        # ... существующий код ...
        
        # Инициализация ML скорера
        self.ml_scorer = get_ml_scorer()
        self.use_ml_scoring = True
    
    def _collect_ohlc_data(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Сбор OHLC данных для всех символов."""
        ohlc_data = {}
        
        for symbol in symbols:
            try:
                from ..data.ingest import fetch_ohlcv_1h
                from ..data.features import build_feature_rows
                
                bars = fetch_ohlcv_1h(symbol, limit=220)
                frows = build_feature_rows(bars)
                
                # Конвертируем в DataFrame
                df = pd.DataFrame(frows)
                ohlc_data[symbol] = df
                
            except Exception as e:
                print(f"⚠️  Ошибка загрузки OHLC для {symbol}: {e}")
                ohlc_data[symbol] = pd.DataFrame()
        
        return ohlc_data
    
    def run_once(self):
        """Основной цикл с ML скорингом."""
        # ... существующий код сбора кандидатов ...
        
        # Сбор OHLC данных для ML
        ohlc_data = self._collect_ohlc_data(self.symbols)
        
        # ... существующий код прогнозирования ...
        
        # ML-улучшенный скоринг
        if self.use_ml_scoring:
            scored = safe_enhanced_score_candidates(
                all_cands, forecasts, btc_weight, ohlc_data
            )
        else:
            scored = original_score_candidates(all_cands, forecasts, btc_weight)
        
        # ... остальной код ...
        
        return scored


# Пример использования в существующем коде
def integrate_ml_scoring_in_existing_pipeline():
    """
    Пример интеграции ML скоринга в существующий пайплайн.
    Показывает минимальные изменения для добавления ML функциональности.
    """
    
    # В orchestrator/engine/pipeline.py
    # Замените вызов score_candidates на:
    
    # Оригинальный код:
    # scored = score_candidates(all_cands, forecasts, btc_weight)
    
    # Новый код с ML:
    from orchestrator.auction.ml_scorer import safe_enhanced_score_candidates
    
    # Сбор OHLC данных для ML
    ohlc_data = {}
    for symbol in self.symbols:
        try:
            bars = fetch_ohlcv_1h(symbol, limit=220)
            frows = build_feature_rows(bars)
            ohlc_data[symbol] = pd.DataFrame(frows)
        except Exception:
            ohlc_data[symbol] = pd.DataFrame()
    
    # ML-улучшенный скоринг
    scored = safe_enhanced_score_candidates(
        all_cands, forecasts, btc_weight, ohlc_data
    )
    
    # Остальной код остается без изменений
    winner = pick_winner(scored)
    # ...


if __name__ == "__main__":
    # Тестирование ML скорера
    print("🔧 Тестирование ML скорера...")
    
    ml_scorer = get_ml_scorer()
    available_models = ml_scorer.get_available_models()
    
    print(f"📊 Доступные модели: {available_models}")
    
    if available_models:
        print("✅ ML скорер готов к использованию")
    else:
        print("⚠️  ML модели не найдены, будет использоваться fallback режим")
