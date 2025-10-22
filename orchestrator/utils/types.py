from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Dict, List, Optional, TypedDict

Side = Literal["LONG", "SHORT"]
SignalType = Literal["BRK", "PB", "TRND", "BB"]

class GuardDecision(str, Enum):
    ACCEPT = "ACCEPT"
    ADAPT = "ADAPT"
    REJECT = "REJECT"

@dataclass
class PairSpec:
    symbol: str
    group: Literal["A", "B"]
    step_size: float
    tick_size: float

@dataclass
class Bar:
    ts: int  # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: float

class FeatureRow(TypedDict, total=False):
    ts: int
    close: float
    atr14: float
    natr14_pct: float
    ema20: float
    ema50: float
    ema200: float
    rsi2: float
    rsi14: float
    adx14: float
    bb_mid: float
    bb_up: float
    bb_low: float
    bb_bw: float  # bandwidth
    dist_to_ema20_atr: float
    mid_slope: float

@dataclass
class SignalCandidate:
    symbol: str
    type: SignalType
    side: Side
    entry_price: float
    atr: float              # ATR14 (1h)
    ema20: float
    meta: Dict[str, float]  # rsi2, adx, bandwidth, dist_to_ema20_atr, etc.
    ts: int                 # unix ms

@dataclass
class FirstHitForecast:
    symbol: str
    type: SignalType
    side: Side
    H: int                  # 2/4/6/10 (часовых баров)
    p_hit: Dict[str, float] # {"tp1":..,"tp2":..,"tp3":..,"tp4":..,"sl":..}
    t_hit: Dict[str, float] # медианные часы до срабатывания каждого барьера
    fill_prob: float
    slip_est: float
    conf_type: float        # уверенность модели данного типа 0..1
    flags: Dict[str, bool]  # exhaustion, inversion и т.д.

@dataclass
class ScoredCandidate:
    symbol: str
    type: SignalType
    side: Side
    H_best: int
    score_usdt: float       # после комиссий/сллипа и временного веса
    components: Dict[str, float]

@dataclass
class ExecutionPlan:
    symbol: str
    side: Side
    qty: float                 # рассчитано из fixed_notional и лотов
    entry_limit: float         # postOnly LIMIT
    ttl_sec: int               # 8–12
    market_fallback_cap: float # max slippage %, напр. 0.12
    tp_levels: List[tuple]     # [(price, qty), ...] — уже в абсолютном количестве
    sl_price: float
