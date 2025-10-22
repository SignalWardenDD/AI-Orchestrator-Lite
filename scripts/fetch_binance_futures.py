# scripts/fetch_binance_futures.py
from __future__ import annotations
import argparse, os, time, math, sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
import pandas as pd

BINANCE_FAPI = "https://fapi.binance.com"
KLINES_EP = "/fapi/v1/klines"  # USDT-M Futures klines
MAX_LIMIT = 1500

DEFAULT_SYMBOLS = [
    "PNUTUSDT", "ADAUSDT", "WIFUSDT", "ENAUSDT", "HBARUSDT",
    "DOGEUSDT", "LTCUSDT", "ARBUSDT", "SUIUSDT", "SEIUSDT",
]

INTERVALS_ALLOWED = {
    "1h": 60 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "1m": 60 * 1000,
}

def to_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

def from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

def http_get(url: str, params: dict, retries: int = 5, timeout: int = 15):
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            # rate limit or temp error → backoff
            last_err = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = repr(e)
        # simple backoff
        time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {last_err}")

def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    url = BINANCE_FAPI + KLINES_EP
    frames = []
    step = INTERVALS_ALLOWED[interval] * (MAX_LIMIT - 1)  # overlap-safe
    cur = start_ms
    while cur < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": cur,
            "endTime": min(cur + step, end_ms),
            "limit": MAX_LIMIT,
        }
        data = http_get(url, params)
        if not data:
            # if empty, jump 1 step
            cur = min(cur + step + INTERVALS_ALLOWED[interval], end_ms)
            time.sleep(0.25)
            continue

        # Binance kline payload description:
        # [0] open time, [1] open, [2] high, [3] low, [4] close, [5] volume,
        # [6] close time, [7] quote asset volume, [8] number of trades,
        # [9] taker buy base, [10] taker buy quote, [11] ignore
        df = pd.DataFrame(data, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","quote_volume","trades","taker_base","taker_quote","ignore"
        ])
        # types
        for c in ("open","high","low","close","volume","quote_volume","taker_base","taker_quote"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        frames.append(df[["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote"]])

        # advance cursor: last kline close_time + 1 ms to avoid duplicates
        last_close_ms = int(data[-1][6])
        cur = last_close_ms + 1

        # gentler rate limit
        time.sleep(0.25)

    if not frames:
        return pd.DataFrame(columns=["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote"])
    out = pd.concat(frames, axis=0).drop_duplicates(subset=["open_time"]).sort_values("open_time")
    return out

def save_csv(df: pd.DataFrame, out_dir: str, symbol: str, interval: str, start_dt: datetime, end_dt: datetime) -> str:
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{symbol}_{interval}_{start_dt.strftime('%Y%m%d')}-{end_dt.strftime('%Y%m%d')}.csv"
    path = os.path.join(out_dir, fname)
    # rename columns to common OHLCV
    pretty = df.rename(columns={
        "open_time": "timestamp",
        "quote_volume": "quote_asset_volume",
        "taker_base": "taker_buy_base",
        "taker_quote": "taker_buy_quote",
    })
    pretty.to_csv(path, index=False)
    return path

def main():
    ap = argparse.ArgumentParser(description="Download Binance USDT-M Futures OHLCV for training.")
    ap.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS),
                    help="Comma-separated list. Default: 10 curated alts.")
    ap.add_argument("--interval", type=str, default="1h", choices=list(INTERVALS_ALLOWED.keys()))
    ap.add_argument("--years", type=int, default=3, help="How many years back from today.")
    ap.add_argument("--start", type=str, default=None, help="Override ISO start (e.g., 2022-01-01).")
    ap.add_argument("--end", type=str, default=None, help="Override ISO end (e.g., 2025-10-22).")
    ap.add_argument("--out", type=str, default="data/raw/binance_futures")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if args.interval not in INTERVALS_ALLOWED:
        print(f"Unsupported interval: {args.interval}", file=sys.stderr)
        sys.exit(2)

    # compute date range
    now_utc = datetime.now(timezone.utc)
    end_dt = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else now_utc
    if args.start:
        start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=365 * args.years)

    start_ms = to_ms(start_dt)
    end_ms = to_ms(end_dt)

    out_dir = os.path.join(args.out, args.interval)
    print(f"Downloading {args.interval} klines from {start_dt.date()} to {end_dt.date()} for {len(symbols)} symbols")
    print(f"Output → {out_dir}")

    for i, sym in enumerate(symbols, 1):
        try:
            print(f"[{i}/{len(symbols)}] {sym} …", end="", flush=True)
            df = fetch_klines(sym, args.interval, start_ms, end_ms)
            if df.empty:
                print(" empty")
                continue
            path = save_csv(df, out_dir, sym, args.interval, start_dt, end_dt)
            rows = df.shape[0]
            first = df["open_time"].iloc[0].strftime("%Y-%m-%d %H:%M")
            last = df["open_time"].iloc[-1].strftime("%Y-%m-%d %H:%M")
            print(f" {rows} bars [{first} → {last}] → {path}")
        except Exception as e:
            print(f" ERROR: {e!r}")

if __name__ == "__main__":
    main()
