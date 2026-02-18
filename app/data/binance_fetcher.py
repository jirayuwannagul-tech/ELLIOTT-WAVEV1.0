import requests
import pandas as pd
from datetime import datetime, timezone


BASE_URL = "https://api.binance.com/api/v3/klines"


def fetch_ohlcv(symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
    """
    Fetch OHLCV data from Binance
    """

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    response = requests.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    df = pd.DataFrame(
        data,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "num_trades",
            "taker_base_vol",
            "taker_quote_vol",
            "ignore",
        ],
    )

    # Convert types
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df[["open_time", "open", "high", "low", "close", "volume"]]

def drop_unclosed_candle(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) < 2:
        return df

    last_open = df["open_time"].iloc[-1]  # pd.Timestamp (UTC)
    prev_open = df["open_time"].iloc[-2]  # pd.Timestamp (UTC)

    interval = last_open - prev_open      # pd.Timedelta
    expected_close = last_open + interval # pd.Timestamp

    now = pd.Timestamp.now(tz="UTC")

    if now < expected_close:
        return df.iloc[:-1].copy()

    return df.copy()