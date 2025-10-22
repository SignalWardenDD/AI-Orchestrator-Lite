# scripts/export_daily_report.py
from __future__ import annotations
import os, argparse, json
from typing import Optional
import pandas as pd
from datetime import datetime

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _safe_read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=["timestamp","opened_at","closed_at"], infer_datetime_format=True)
    except Exception:
        # Фолбэк без явных колонок времени
        return pd.read_csv(path)

def _fallback_daily(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Минимальный дневной отчёт, если нет telemetry.reports.
    Ожидаемые колонки (best-effort): symbol, side, pnl_usdt, opened_at/closed_at.
    """
    df = trades.copy()
    # определим дату по закрытию либо открытию
    if "closed_at" in df.columns:
        dt = pd.to_datetime(df["closed_at"], errors="coerce")
    elif "opened_at" in df.columns:
        dt = pd.to_datetime(df["opened_at"], errors="coerce")
    else:
        dt = pd.to_datetime(df.get("timestamp", pd.Timestamp.utcnow()), errors="coerce")

    df["date"] = dt.dt.tz_localize(None).dt.date
    grp = df.groupby("date", dropna=False)
    out = pd.DataFrame({
        "trades": grp.size(),
        "win_trades": grp.apply(lambda g: (g.get("pnl_usdt", 0) > 0).sum()),
        "loss_trades": grp.apply(lambda g: (g.get("pnl_usdt", 0) <= 0).sum()),
        "pnl_usdt": grp["pnl_usdt"].sum() if "pnl_usdt" in df.columns else 0.0,
        "avg_pnl": grp["pnl_usdt"].mean() if "pnl_usdt" in df.columns else 0.0,
    }).reset_index()
    return out

def main():
    ap = argparse.ArgumentParser(description="Export daily report CSV from telemetry logs.")
    ap.add_argument("--telemetry_dir", type=str, required=True,
                    help="Directory with telemetry CSVs (e.g., trades.csv, orders.csv).")
    ap.add_argument("--out_dir", type=str, default="reports")
    ap.add_argument("--tz", type=str, default=None, help="Optional timezone (e.g., Europe/Kyiv) for date bucketing.")
    args = ap.parse_args()

    _ensure_dir(args.out_dir)

    trades_csv = os.path.join(args.telemetry_dir, "trades.csv")
    trades = _safe_read_csv(trades_csv)

    # Попытка использовать официальную реализацию, если есть
    try:
        from telemetry.reports import daily_report_from_trades  # предполагаемая функция
        rep = daily_report_from_trades(trades, tz=args.tz)
        mode = "telemetry.reports"
    except Exception:
        rep = _fallback_daily(trades)
        mode = "fallback"

    today = datetime.utcnow().strftime("%Y-%m-%d")
    out_path = os.path.join(args.out_dir, f"daily_report_{today}.csv")
    rep.to_csv(out_path, index=False)

    print(json.dumps({
        "ok": True,
        "mode": mode,
        "rows": int(rep.shape[0]),
        "out_csv": out_path
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()