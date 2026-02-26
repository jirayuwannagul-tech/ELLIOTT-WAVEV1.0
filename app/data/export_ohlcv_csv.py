# app/data/export_ohlcv_csv.py
from __future__ import annotations

import argparse
import os
import time

import pandas as pd
import requests

from app.data.binance_fetcher import drop_unclosed_candle

BASE_URL = "https://api.binance.com/api/v3/klines"
_BINANCE_MAX_PER_CALL = 1000


def _fetch_ohlcv_paginated(
    symbol: str,
    interval: str,
    total_limit: int,
) -> pd.DataFrame:
    """
    Fetch OHLCV จาก Binance แบบ paginated
    Binance จำกัด 1000 bars ต่อ 1 call → ต้อง loop หลาย call
    ใช้ endTime เพื่อดึงข้อมูลย้อนหลัง
    """
    all_rows = []
    end_time: int | None = None  # None = ล่าสุด, จากนั้นใช้ open_time แรก - 1ms

    remaining = total_limit

    while remaining > 0:
        batch_size = min(remaining, _BINANCE_MAX_PER_CALL)

        params: dict = {
            "symbol":   symbol,
            "interval": interval,
            "limit":    batch_size,
        }
        if end_time is not None:
            params["endTime"] = end_time

        try:
            resp = requests.get(BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[WARN] fetch error: {e} → หยุด pagination")
            break

        if not data:
            break

        # data เรียงจากเก่า → ใหม่
        all_rows = data + all_rows  # prepend (เก่ากว่าไว้หน้า)
        remaining -= len(data)

        if len(data) < batch_size:
            # ข้อมูลหมดแล้ว ไม่ต้อง fetch ต่อ
            break

        # เลื่อน endTime ไปก่อนหน้า candle แรกที่ได้มา
        first_open_time = int(data[0][0])
        end_time = first_open_time - 1

        time.sleep(0.2)  # กัน rate limit

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        all_rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "num_trades",
            "taker_base_vol", "taker_quote_vol", "ignore",
        ],
    )

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()

    # กัน duplicate rows (อาจเกิดจาก pagination overlap)
    df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol",   required=True)
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--limit",    type=int, default=1500)
    ap.add_argument("--out",      default="data")
    args = ap.parse_args()

    print(f"Fetching {args.symbol} {args.interval} limit={args.limit} ...")

    df = _fetch_ohlcv_paginated(args.symbol, args.interval, args.limit)
    df = drop_unclosed_candle(df)

    if df is None or df.empty:
        raise SystemExit("fetch returned empty df")

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, f"{args.symbol}_{args.interval}.csv")
    df.to_csv(out_path, index=True)
    print(f"OK: saved {out_path} rows={len(df)} cols={list(df.columns)}")


if __name__ == "__main__":
    main()