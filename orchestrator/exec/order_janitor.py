# orchestrator/exec/order_janitor.py
"""
«Янитор» — координация сверки ордеров по всем символам.
Периодически запускает идемпотентную синхронизацию с биржей.
"""

from __future__ import annotations
from time import time
from typing import Dict, List, Optional

class OrderJanitor:
    """
    Координатор сверки ордеров с биржей.
    Запускается периодически и синхронизирует состояние ордеров.
    """
    
    def __init__(self, cfg, broker, tracker):
        self.cfg = cfg
        self.broker = broker
        self.tracker = tracker
        self._last_run_ts = 0.0

    def maybe_run(self, symbols: List[str]) -> Optional[Dict[str, dict]]:
        """
        Запускает сверку если прошло достаточно времени.
        
        Args:
            symbols: Список символов для сверки
            
        Returns:
            Отчет о сверке или None если не запускалась
        """
        if not self.cfg.reconciliation.enabled:
            return None
            
        now = time()
        if now - self._last_run_ts < self.cfg.reconciliation.interval_seconds:
            return None
            
        self._last_run_ts = now

        from .reconciler import reconcile_symbol
        report = {}
        
        for sym in symbols:
            try:
                rep = reconcile_symbol(self.cfg, self.broker, self.tracker, sym)
                report[sym] = rep
            except Exception as e:
                report[sym] = {"error": str(e)}
                
        return report

    def force_run(self, symbols: List[str]) -> Dict[str, dict]:
        """
        Принудительно запускает сверку для всех символов.
        
        Args:
            symbols: Список символов для сверки
            
        Returns:
            Отчет о сверке
        """
        from .reconciler import reconcile_symbol
        report = {}
        
        for sym in symbols:
            try:
                rep = reconcile_symbol(self.cfg, self.broker, self.tracker, sym)
                report[sym] = rep
            except Exception as e:
                report[sym] = {"error": str(e)}
                
        return report
