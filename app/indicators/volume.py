import pandas as pd


def add_volume_ma(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """
    Add Volume Moving Average
    expects column: volume
    """

    out = df.copy()
    out[f"vol_ma{length}"] = out["volume"].rolling(length).mean()
    return out


def volume_spike(df: pd.DataFrame, length: int = 20, multiplier: float = 1.5) -> bool:
    """
    Check if latest volume > multiplier × volume MA
    """

    if len(df) < length + 1:
        return False

    vol = df["volume"].iloc[-1]
    vol_ma = df[f"vol_ma{length}"].iloc[-1]

    if pd.isna(vol_ma):
        return False

    return vol > vol_ma * multiplier