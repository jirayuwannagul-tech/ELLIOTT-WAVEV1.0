import logging
import time

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com/api/v3/klines"
_MAX_RETRY = 3
_RETRY_DELAY = 5  # วินาที


def fetch_ohlcv(symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    last_error = None

    for attempt in range(1, _MAX_RETRY + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            df = pd.DataFrame(
                data,
                columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "qav", "num_trades",
                    "taker_base_vol", "taker_quote_vol", "ignore",
                ],
            )

            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            return df[["open_time", "open", "high", "low", "close", "volume"]]

        except requests.exceptions.Timeout:
            last_error = "timeout"
            logger.warning(f"[{symbol}] fetch timeout attempt={attempt}/{_MAX_RETRY}")

        except requests.exceptions.ConnectionError:
            last_error = "connection error"
            logger.warning(f"[{symbol}] connection error attempt={attempt}/{_MAX_RETRY}")

        except requests.exceptions.HTTPError as e:
            last_error = str(e)
            logger.warning(f"[{symbol}] HTTP error {e} attempt={attempt}/{_MAX_RETRY}")

        except Exception as e:
            last_error = str(e)
            logger.error(f"[{symbol}] unexpected error {e} attempt={attempt}/{_MAX_RETRY}")

        if attempt < _MAX_RETRY:
            time.sleep(_RETRY_DELAY)

    logger.error(f"[{symbol}] fetch_ohlcv ล้มเหลวทุก {_MAX_RETRY} ครั้ง: {last_error}")
    return pd.DataFrame()


def drop_unclosed_candle(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) < 2:
        return df

    try:
        last_open = df["open_time"].iloc[-1]
        prev_open = df["open_time"].iloc[-2]
        interval = last_open - prev_open
        expected_close = last_open + interval
        now = pd.Timestamp.now(tz="UTC")

        if now < expected_close:
            return df.iloc[:-1].copy()

        return df.copy()

    except Exception as e:
        logger.error(f"drop_unclosed_candle error: {e}")
        return df.copy()
