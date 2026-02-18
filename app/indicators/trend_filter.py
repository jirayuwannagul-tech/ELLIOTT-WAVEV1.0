import pandas as pd


def trend_filter_ema(df: pd.DataFrame) -> str:
    """
    Trend filter using EMA50/EMA200
    expects columns: ema50, ema200, close

    returns: "BULL", "BEAR", "NEUTRAL"
    """
    if "ema50" not in df.columns or "ema200" not in df.columns:
        return "NEUTRAL"

    close = df["close"].iloc[-1]
    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    if pd.isna(ema50) or pd.isna(ema200):
        return "NEUTRAL"

    if close > ema50 > ema200:
        return "BULL"
    if close < ema50 < ema200:
        return "BEAR"
    return "NEUTRAL"


def allow_direction(macro_trend: str, direction: str) -> bool:
    """
    Allow trade direction based on macro trend
    - BULL: allow LONG
    - BEAR: allow SHORT
    - NEUTRAL: allow both but treat as lower confidence
    """
    macro_trend = (macro_trend or "").upper()
    direction = (direction or "").upper()

    if macro_trend == "BULL":
        return direction == "LONG"
    if macro_trend == "BEAR":
        return direction == "SHORT"
    return True