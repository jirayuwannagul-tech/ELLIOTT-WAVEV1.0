import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    """
    Exponential Moving Average (EMA)
    """
    return series.ewm(span=length, adjust=False).mean()


def add_ema(df: pd.DataFrame, lengths=(50, 200)) -> pd.DataFrame:
    """
    Add EMA columns to df
    - expects df has 'close'
    """
    out = df.copy()
    for L in lengths:
        out[f"ema{L}"] = ema(out["close"], L)
    return out