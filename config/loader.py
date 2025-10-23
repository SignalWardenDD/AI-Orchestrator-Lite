from __future__ import annotations
import os, yaml
from dataclasses import dataclass
from typing import Any, Dict

CFG_ROOT = os.path.join(os.path.dirname(__file__))

@dataclass
class SettingsCfg:
    engine: Dict[str, Any]
    btc_context: Dict[str, Any]
    ml: Dict[str, Any] = None

@dataclass
class RiskCfg:
    position: Dict[str, Any]
    limits: Dict[str, Any]
    sl_multipliers: Dict[str, float]

@dataclass
class LaddersCfg:
    tp: list[dict]  # [{pct, atr_mult}]
    be: Dict[str, float]  # after_tp1_usdt, after_tp2_usdt, after_tp3_usdt

@dataclass
class SymbolsCfg:
    symbols: list[dict]

def _load_yaml(name: str) -> Dict[str, Any]:
    path = os.path.join(CFG_ROOT, name)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings() -> SettingsCfg:
    y = _load_yaml("settings.yaml")
    return SettingsCfg(
        engine=y.get("engine", {}), 
        btc_context=y.get("btc_context", {}),
        ml=y.get("ml", {})
    )


def load_risk() -> RiskCfg:
    y = _load_yaml("risk.yaml")
    return RiskCfg(position=y.get("position", {}), limits=y.get("limits", {}), sl_multipliers=y.get("sl_multipliers", {}))


def load_ladders() -> LaddersCfg:
    y = _load_yaml("ladders.yaml")
    return LaddersCfg(tp=y.get("tp", []), be=y.get("be", {}))


def load_symbols() -> SymbolsCfg:
    y = _load_yaml("symbols.yaml")
    out = []
    
    # Поддержка старого формата
    if "symbols" in y and isinstance(y["symbols"], list):
        out = y["symbols"]
    else:
        # Новый формат с группами
        for group_key in ("A_group", "B_group"):
            grp = y.get(group_key, {})
            for sym, params in grp.items():
                item = {"symbol": sym}
                item.update(params or {})
                out.append(item)
    
    return SymbolsCfg(symbols=out)
