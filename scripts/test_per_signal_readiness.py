#!/usr/bin/env python3
"""
Проверка готовности к обучению per-signal моделей.
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append('.')

from orchestrator.data.loader import load_signal_marks_df

SYMS = ["ADAUSDT","HBARUSDT","LTCUSDT","PNUTUSDT","WIFUSDT","ENAUSDT","DOGEUSDT","ARBUSDT","SUIUSDT","SEIUSDT"]

def main():
    print("🔍 Проверка готовности к обучению per-signal моделей...")
    print("=" * 60)
    
    missing = []
    total_marks = 0
    
    for s in SYMS:
        try:
            df = load_signal_marks_df(s)
            assert set(["BRK","PB","MR","BB"]).issubset(df.columns)
            marks_count = df[["BRK","PB","MR","BB"]].sum().sum()
            total_marks += marks_count
            print(f"[OK] {s}: marks {len(df)} rows, signals {marks_count}")
        except Exception as e:
            print(f"[MISS] {s}: {e}")
            missing.append(s)
    
    print("\n" + "=" * 60)
    print(f"📊 ИТОГО: {len(SYMS) - len(missing)}/{len(SYMS)} символов готовы")
    print(f"📊 Всего меток сигналов: {total_marks}")
    
    if missing:
        print(f"\n❌ Отсутствуют метки для: {', '.join(missing)}")
        print(f"\nЧтобы исправить:")
        print(f"  python3 scripts/build_signal_marks.py --symbols {' '.join(missing)}")
        print(f"\nИли для всех символов:")
        print(f"  make build-signal-marks")
        sys.exit(1)
    else:
        print(f"\n✅ Все символы готовы к обучению per-signal моделей!")
        print(f"🚀 Можно запускать: make per-signal-all")

if __name__ == "__main__":
    main()
