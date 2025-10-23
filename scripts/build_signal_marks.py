#!/usr/bin/env python3
"""
Построение и кэш меток сигналов для per-signal моделей.
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np

# Добавляем путь к проекту
import sys
sys.path.append('.')

from orchestrator.data.loader import load_kline_df
from orchestrator.utils.io import ensure_dir

def compute_brk_marks(kline: pd.DataFrame) -> pd.Series:
    """
    Вычисляет метки Breakout сигналов.
    Простая логика: прорыв выше максимума последних 20 баров.
    """
    high_20 = kline["high"].rolling(20, min_periods=20).max()
    marks = (kline["close"] > high_20.shift(1)) & (kline["close"] > kline["open"])
    return marks.astype(int)

def compute_pb_marks(kline: pd.DataFrame) -> pd.Series:
    """
    Вычисляет метки Pullback сигналов.
    Простая логика: откат к EMA20 после роста.
    """
    ema20 = kline["close"].ewm(span=20).mean()
    marks = (kline["close"] < ema20) & (kline["close"].shift(1) > ema20.shift(1))
    return marks.astype(int)

def compute_mr_marks(kline: pd.DataFrame) -> pd.Series:
    """
    Вычисляет метки Mean Reversion сигналов.
    Простая логика: цена далеко от EMA50.
    """
    ema50 = kline["close"].ewm(span=50).mean()
    distance = abs(kline["close"] - ema50) / ema50
    marks = distance > 0.05  # 5% отклонение
    return marks.astype(int)

def compute_bb_marks(kline: pd.DataFrame) -> pd.Series:
    """
    Вычисляет метки Bollinger Bands сигналов.
    Простая логика: касание верхней или нижней полосы.
    """
    ema20 = kline["close"].ewm(span=20).mean()
    std20 = kline["close"].rolling(20, min_periods=20).std()
    upper = ema20 + 2 * std20
    lower = ema20 - 2 * std20
    
    marks = (kline["close"] >= upper) | (kline["close"] <= lower)
    return marks.astype(int)

def build_for_symbol(symbol: str, out_dir: Path):
    """Строит метки сигналов для символа."""
    try:
        kline = load_kline_df(symbol)  # index = close_time (UTC), columns: open,high,low,close,volume, ...
        marks = pd.DataFrame(index=kline.index)
        marks["BRK"] = compute_brk_marks(kline).astype("int8")
        marks["PB"]  = compute_pb_marks(kline).astype("int8")
        marks["MR"]  = compute_mr_marks(kline).astype("int8")
        marks["BB"]  = compute_bb_marks(kline).astype("int8")

        ensure_dir(out_dir)
        path = out_dir / f"{symbol}.parquet"
        marks.to_parquet(path, index=True)
        return str(path), int(marks["BRK"].sum()), int(marks["PB"].sum()), int(marks["MR"].sum()), int(marks["BB"].sum())
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
        return None, 0, 0, 0, 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--out_dir", default="data/signals")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"🔍 Генерация меток сигналов для {len(args.symbols)} символов...")
    print(f"📁 Выходная директория: {out}")
    
    total_brk = total_pb = total_mr = total_bb = 0
    
    for sym in args.symbols:
        result = build_for_symbol(sym, out)
        if result[0]:  # path exists
            path, n_brk, n_pb, n_mr, n_bb = result
            print(f"[OK] {sym} → {path} | BRK={n_brk} PB={n_pb} MR={n_mr} BB={n_bb}")
            total_brk += n_brk
            total_pb += n_pb
            total_mr += n_mr
            total_bb += n_bb
        else:
            print(f"[SKIP] {sym} - ошибка генерации")
    
    print(f"\n📊 ИТОГО меток:")
    print(f"  BRK: {total_brk}")
    print(f"  PB:  {total_pb}")
    print(f"  MR:  {total_mr}")
    print(f"  BB:  {total_bb}")
    print(f"  Всего: {total_brk + total_pb + total_mr + total_bb}")

if __name__ == "__main__":
    main()
