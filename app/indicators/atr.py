import pandas as pd


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """
    ATR (Wilder)
    expects columns: high, low, close
    """

    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return true_range.ewm(alpha=1 / length, adjust=False).mean()


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    out = df.copy()
    out[f"atr{length}"] = atr(out, length)
    return out
    