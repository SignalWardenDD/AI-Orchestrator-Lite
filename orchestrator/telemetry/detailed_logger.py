# orchestrator/telemetry/detailed_logger.py
"""
Детальная система логирования для торговой системы.
Обеспечивает полную прозрачность всех решений и процессов.
"""

from __future__ import annotations
import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class TradingDecision:
    """Структура торгового решения."""
    timestamp: str
    cycle_id: str
    symbol: str
    decision: str  # ACCEPT, REJECT, BLOCK, SKIP
    reason: str
    score: Optional[float] = None
    ml_probability: Optional[float] = None
    ev_usdt: Optional[float] = None
    context: Optional[Dict[str, Any]] = None

@dataclass
class OrderEvent:
    """Событие ордера."""
    timestamp: str
    cycle_id: str
    event_type: str  # PLACED, FILLED, CANCELLED, EXPIRED
    symbol: str
    order_id: str
    side: str
    qty: float
    price: float
    role: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class SystemStatus:
    """Статус системы."""
    timestamp: str
    cycle_id: str
    active_positions: int
    pending_orders: int
    ml_models_loaded: int
    last_sync_time: Optional[str] = None
    errors_count: int = 0

class DetailedLogger:
    """
    Детальный логгер для торговой системы.
    Обеспечивает полную прозрачность всех процессов.
    """
    
    def __init__(self, name: str = "trading_system"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Настройка форматтера
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Консольный хендлер
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Файловый хендлер
        file_handler = logging.FileHandler('trading_system_detailed.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # JSON хендлер для структурированных логов
        json_handler = logging.FileHandler('trading_system_structured.json')
        json_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(json_handler)
        
        self.cycle_id = self._generate_cycle_id()
        self.decisions_count = 0
        self.orders_count = 0
        
    def _generate_cycle_id(self) -> str:
        """Генерирует уникальный ID цикла."""
        return f"CYCLE_{int(time.time() * 1000)}"
    
    def _get_timestamp(self) -> str:
        """Возвращает текущий timestamp в UTC."""
        return datetime.now(timezone.utc).isoformat()
    
    def log_cycle_start(self, symbols: List[str], ml_enabled: bool = True):
        """Логирует начало цикла анализа."""
        self.cycle_id = self._generate_cycle_id()
        
        cycle_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "CYCLE_START",
            "symbols": symbols,
            "ml_enabled": ml_enabled,
            "total_symbols": len(symbols)
        }
        
        self.logger.info(f"🔄 CYCLE_START: {json.dumps(cycle_info)}")
        print(f"🔄 Начинаем цикл анализа {self.cycle_id} для {len(symbols)} символов")
    
    def log_signal_generation(self, symbol: str, signals: List[Dict[str, Any]]):
        """Логирует генерацию сигналов для символа."""
        signal_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "SIGNAL_GENERATION",
            "symbol": symbol,
            "signals_count": len(signals),
            "signals": signals
        }
        
        self.logger.info(f"📊 SIGNAL_GENERATION: {json.dumps(signal_info)}")
        print(f"📊 {symbol}: сгенерировано {len(signals)} сигналов")
        
        for signal in signals:
            print(f"    - {signal.get('type', 'UNKNOWN')} {signal.get('side', 'UNKNOWN')}: {signal.get('entry_price', 0):.4f}")
    
    def log_ml_prediction(self, symbol: str, features: Dict[str, float], 
                         h12_prob: float, h24_prob: float, ensemble_prob: float):
        """Логирует ML предсказание."""
        ml_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "ML_PREDICTION",
            "symbol": symbol,
            "features": features,
            "h12_probability": h12_prob,
            "h24_probability": h24_prob,
            "ensemble_probability": ensemble_prob
        }
        
        self.logger.info(f"🤖 ML_PREDICTION: {json.dumps(ml_info)}")
        print(f"🤖 {symbol} ML: H12={h12_prob:.3f}, H24={h24_prob:.3f}, Ensemble={ensemble_prob:.3f}")
    
    def log_scoring(self, candidates: List[Dict[str, Any]], best_candidate: Optional[Dict[str, Any]]):
        """Логирует процесс скоринга."""
        scoring_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "SCORING",
            "candidates_count": len(candidates),
            "candidates": candidates,
            "best_candidate": best_candidate
        }
        
        self.logger.info(f"🎯 SCORING: {json.dumps(scoring_info)}")
        print(f"🎯 Скоринг: {len(candidates)} кандидатов")
        
        if best_candidate:
            print(f"    🏆 Лучший: {best_candidate.get('symbol')} {best_candidate.get('side')} "
                  f"(score: {best_candidate.get('score_usdt', 0):.3f} USDT)")
        else:
            print("    ❌ Нет подходящих кандидатов")
    
    def log_decision(self, symbol: str, decision: str, reason: str, 
                    score: Optional[float] = None, ml_prob: Optional[float] = None,
                    ev_usdt: Optional[float] = None, context: Optional[Dict[str, Any]] = None):
        """Логирует торговое решение."""
        self.decisions_count += 1
        
        decision_obj = TradingDecision(
            timestamp=self._get_timestamp(),
            cycle_id=self.cycle_id,
            symbol=symbol,
            decision=decision,
            reason=reason,
            score=score,
            ml_probability=ml_prob,
            ev_usdt=ev_usdt,
            context=context
        )
        
        decision_data = asdict(decision_obj)
        self.logger.info(f"⚖️ TRADING_DECISION: {json.dumps(decision_data)}")
        
        # Цветное логирование в консоль
        decision_emoji = {
            "ACCEPT": "✅",
            "REJECT": "❌", 
            "BLOCK": "🚫",
            "SKIP": "⏭️"
        }.get(decision, "❓")
        
        print(f"{decision_emoji} {symbol}: {decision} - {reason}")
        if score is not None:
            print(f"    📊 Score: {score:.3f} USDT")
        if ml_prob is not None:
            print(f"    🤖 ML Prob: {ml_prob:.3f}")
        if ev_usdt is not None:
            print(f"    💰 EV: {ev_usdt:.3f} USDT")
    
    def log_order_placed(self, symbol: str, order_id: str, side: str, qty: float, 
                        price: float, role: str, order_type: str = "LIMIT"):
        """Логирует размещение ордера."""
        self.orders_count += 1
        
        order_event = OrderEvent(
            timestamp=self._get_timestamp(),
            cycle_id=self.cycle_id,
            event_type="PLACED",
            symbol=symbol,
            order_id=order_id,
            side=side,
            qty=qty,
            price=price,
            role=role,
            details={"order_type": order_type}
        )
        
        order_data = asdict(order_event)
        self.logger.info(f"📝 ORDER_PLACED: {json.dumps(order_data)}")
        
        print(f"📝 Ордер размещен: {symbol} {side} {qty:.4f} @ {price:.4f} ({role})")
        print(f"    🆔 Order ID: {order_id}")
    
    def log_order_filled(self, symbol: str, order_id: str, side: str, qty: float, 
                        price: float, role: str, pnl_usdt: float = 0.0):
        """Логирует исполнение ордера."""
        order_event = OrderEvent(
            timestamp=self._get_timestamp(),
            cycle_id=self.cycle_id,
            event_type="FILLED",
            symbol=symbol,
            order_id=order_id,
            side=side,
            qty=qty,
            price=price,
            role=role,
            details={"pnl_usdt": pnl_usdt}
        )
        
        order_data = asdict(order_event)
        self.logger.info(f"💰 ORDER_FILLED: {json.dumps(order_data)}")
        
        pnl_emoji = "📈" if pnl_usdt > 0 else "📉" if pnl_usdt < 0 else "➡️"
        print(f"💰 Ордер исполнен: {symbol} {side} {qty:.4f} @ {price:.4f}")
        print(f"    {pnl_emoji} PnL: {pnl_usdt:.3f} USDT")
    
    def log_order_cancelled(self, symbol: str, order_id: str, reason: str):
        """Логирует отмену ордера."""
        order_event = OrderEvent(
            timestamp=self._get_timestamp(),
            cycle_id=self.cycle_id,
            event_type="CANCELLED",
            symbol=symbol,
            order_id=order_id,
            side="",
            qty=0.0,
            price=0.0,
            role="",
            details={"reason": reason}
        )
        
        order_data = asdict(order_event)
        self.logger.info(f"❌ ORDER_CANCELLED: {json.dumps(order_data)}")
        
        print(f"❌ Ордер отменен: {symbol} {order_id} - {reason}")
    
    def log_janitor_sync(self, report: Dict[str, Any]):
        """Логирует синхронизацию с биржей."""
        sync_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "JANITOR_SYNC",
            "report": report
        }
        
        self.logger.info(f"🔄 JANITOR_SYNC: {json.dumps(sync_info)}")
        
        total_canceled = sum(r.get("canceled", 0) for r in report.values() if isinstance(r, dict))
        total_created = sum(r.get("created", 0) for r in report.values() if isinstance(r, dict))
        
        print(f"🔄 Синхронизация с биржей: отменено {total_canceled}, создано {total_created}")
        
        for symbol, symbol_report in report.items():
            if isinstance(symbol_report, dict) and "error" not in symbol_report:
                print(f"    {symbol}: отменено {symbol_report.get('canceled', 0)}, "
                      f"создано {symbol_report.get('created', 0)}")
    
    def log_sl_adjustment(self, symbol: str, old_sl: float, new_sl: float, 
                         pnl_usdt: float, reason: str):
        """Логирует корректировку стоп-лосса."""
        sl_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "SL_ADJUSTMENT",
            "symbol": symbol,
            "old_sl": old_sl,
            "new_sl": new_sl,
            "pnl_usdt": pnl_usdt,
            "reason": reason
        }
        
        self.logger.info(f"🛡️ SL_ADJUSTMENT: {json.dumps(sl_info)}")
        print(f"🛡️ SL скорректирован: {symbol} {old_sl:.4f} -> {new_sl:.4f} (PnL: {pnl_usdt:.3f} USDT)")
        print(f"    📝 Причина: {reason}")
    
    def log_error(self, error_type: str, message: str, symbol: Optional[str] = None, 
                  context: Optional[Dict[str, Any]] = None):
        """Логирует ошибку."""
        error_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "ERROR",
            "error_type": error_type,
            "message": message,
            "symbol": symbol,
            "context": context
        }
        
        self.logger.error(f"🚨 ERROR: {json.dumps(error_info)}")
        print(f"🚨 ОШИБКА [{error_type}]: {message}")
        if symbol:
            print(f"    📍 Символ: {symbol}")
    
    def log_system_status(self, active_positions: int, pending_orders: int, 
                         ml_models_loaded: int, errors_count: int = 0):
        """Логирует статус системы."""
        status = SystemStatus(
            timestamp=self._get_timestamp(),
            cycle_id=self.cycle_id,
            active_positions=active_positions,
            pending_orders=pending_orders,
            ml_models_loaded=ml_models_loaded,
            errors_count=errors_count
        )
        
        status_data = asdict(status)
        self.logger.info(f"📊 SYSTEM_STATUS: {json.dumps(status_data)}")
        
        print(f"📊 Статус системы: позиций {active_positions}, ордеров {pending_orders}, "
              f"ML моделей {ml_models_loaded}, ошибок {errors_count}")
    
    def log_cycle_end(self, total_decisions: int, total_orders: int, 
                     execution_time_ms: float):
        """Логирует окончание цикла."""
        cycle_end_info = {
            "timestamp": self._get_timestamp(),
            "cycle_id": self.cycle_id,
            "event": "CYCLE_END",
            "total_decisions": total_decisions,
            "total_orders": total_orders,
            "execution_time_ms": execution_time_ms
        }
        
        self.logger.info(f"🏁 CYCLE_END: {json.dumps(cycle_end_info)}")
        print(f"🏁 Цикл завершен: решений {total_decisions}, ордеров {total_orders}, "
              f"время {execution_time_ms:.1f}мс")

# Глобальный экземпляр логгера
detailed_logger = DetailedLogger()
