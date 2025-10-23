# risk/filters.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import pandas as pd

from ..utils.mathx import natr, rolling_corr, clamp


GuardResult = Tuple[bool, str, Dict]


@dataclass
class CalmMarketGuard:
    """
    Blocks trading when market is too calm (low NATR).
    Use on 1h OHLC with default NATR(14). Threshold in percent.
    """
    threshold_pct: float = 0.80
    lookback: int = 14

    def check(self, ohlc: pd.DataFrame) -> GuardResult:
        # expects columns: high, low, close
        series = natr(ohlc["high"], ohlc["low"], ohlc["close"], period=self.lookback)
        value = float(series.iloc[-1])
        allowed = value >= self.threshold_pct
        return allowed, (
            "ok"
            if allowed else f"CALM_BLOCK: NATR={value:.2f}% < {self.threshold_pct:.2f}%"
        ), {"natr": value, "threshold": self.threshold_pct}


@dataclass
class HourOfDayBlocker:
    """
    Blocks trading in specific hours, e.g., during illiquid or news hours.
    hours_blocked: set of 0..23
    """
    hours_blocked: Optional[set] = None

    def check(self, now_ts) -> GuardResult:
        if not self.hours_blocked:
            return True, "ok", {}
        hour = int(pd.Timestamp(now_ts).hour)
        if hour in self.hours_blocked:
            return False, f"HOUR_BLOCK: hour={hour} in {sorted(self.hours_blocked)}", {"hour": hour}
        return True, "ok", {"hour": hour}


@dataclass
class CorrBlocker:
    """
    Blocks entry when symbol is overly correlated to BTC (or another index),
    to avoid duplicated exposure or to enforce diversification.
    """
    window: int = 48
    max_corr: float = 0.95  # block if |corr| >= max_corr

    def check(self, sym_close: pd.Series, ref_close: pd.Series) -> GuardResult:
        corr_series = rolling_corr(sym_close.pct_change().fillna(0.0),
                                   ref_close.pct_change().fillna(0.0),
                                   window=self.window)
        corr_val = float(corr_series.iloc[-1])
        if abs(corr_val) >= self.max_corr:
            return False, f"CORR_BLOCK: |corr|={abs(corr_val):.2f} >= {self.max_corr:.2f}", {
                "corr": corr_val, "window": self.window
            }
        return True, "ok", {"corr": corr_val}


@dataclass
class SpikeGuard:
    """
    Blocks entry on abnormal one-bar spikes that often revert immediately.
    Uses z-percent move of the last bar vs median of recent bars.
    """
    window: int = 24
    spike_mult: float = 4.0  # block if |last_move| > spike_mult * median(|moves|)

    def check(self, close: pd.Series) -> GuardResult:
        moves = close.pct_change().dropna().tail(self.window)
        if len(moves) < max(5, self.window // 3):
            return True, "ok", {}
        med = float(moves.abs().median())
        last_mv = float(moves.iloc[-1])
        # guard for zero med:
        threshold = med * self.spike_mult if med > 0 else 0.0
        if med > 0 and abs(last_mv) > threshold:
            return False, f"SPIKE_BLOCK: |{last_mv:.4f}| > {threshold:.4f}", {
                "last_move": last_mv, "median_abs": med, "threshold": threshold
            }
        return True, "ok", {"last_move": last_mv, "median_abs": med}


@dataclass
class PositionConcentrationGuard:
    """
    Limits number of concurrent positions per direction or per group.
    """
    max_total: int = 7
    max_per_symbol: int = 1
    max_per_direction: int = 7  # usually same as total for single-position systems

    def check(self, active_positions: pd.DataFrame, candidate_symbol: str, candidate_side: str) -> GuardResult:
        # active_positions columns expected: ["symbol", "side", ...]
        total = len(active_positions)
        per_sym = int((active_positions["symbol"] == candidate_symbol).sum()) if not active_positions.empty else 0
        per_dir = int((active_positions["side"] == candidate_side).sum()) if not active_positions.empty else 0

        if total >= self.max_total:
            return False, f"CONC_BLOCK: total={total} >= {self.max_total}", {"total": total}

        if per_sym >= self.max_per_symbol:
            return False, f"CONC_BLOCK: {candidate_symbol} count={per_sym} >= {self.max_per_symbol}", {
                "per_symbol": per_sym
            }

        if per_dir >= self.max_per_direction:
            return False, f"CONC_BLOCK: side({candidate_side})={per_dir} >= {self.max_per_direction}", {
                "per_direction": per_dir
            }

        return True, "ok", {"total": total, "per_symbol": per_sym, "per_direction": per_dir}

def check_daily_loss(daily_pnl: float, daily_limit: float) -> bool:
    """Проверяет дневные потери."""
    return daily_pnl >= daily_limit

def check_position_limits(current_positions: int, max_positions: int) -> bool:
    """Проверяет лимиты позиций."""
    return current_positions < max_positions