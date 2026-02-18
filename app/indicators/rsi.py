import pandas as pd


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """
    RSI (Wilder)
    """
    delta = close.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-12)
    out = 100 - (100 / (1 + rs))
    return out


def add_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """
    Add RSI column to df
    - expects df has 'close'
    """
    out = df.copy()
    out[f"rsi{length}"] = rsi(out["close"], length)
    return out
    