from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from app.data.binance_fetcher import fetch_ohlcv, drop_unclosed_candle
from app.indicators.ema import add_ema
from app.indicators.rsi import add_rsi
from app.indicators.atr import add_atr
from app.indicators.trend_filter import trend_filter_ema
from app.analysis.pivot import find_fractal_pivots, filter_pivots


@dataclass
class MTFSummary:
    symbol: str
    weekly_trend: str        # BULL/BEAR/NEUTRAL
    h4_trend: str            # BULL/BEAR/NEUTRAL
    weekly_permit_long: bool
    weekly_permit_short: bool
    h4_confirm_long: bool
    h4_confirm_short: bool
    notes: str = ""


def _prepare_df(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    df = fetch_ohlcv(symbol, interval=interval, limit=limit)
    df = drop_unclosed_candle(df)
    if df is None or len(df) == 0:
        return pd.DataFrame()

    # Indicators needed
    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    return df


def _last_close(df: pd.DataFrame) -> Optional[float]:
    try:
        return float(df["close"].iloc[-1])
    except Exception:
        return None


def _h4_structure_confirm(df4h: pd.DataFrame) -> Tuple[bool, bool, str]:
    """
    Confirm แบบง่าย (ไม่ยาว):
    - LONG confirm: close > last pivot-high price
    - SHORT confirm: close < last pivot-low price
    """
    if df4h is None or len(df4h) < 250:
        return False, False, "4H len<250"

    close = _last_close(df4h)
    if close is None:
        return False, False, "4H no close"

    pivots = find_fractal_pivots(df4h, left=2, right=2)
    pivots = filter_pivots(pivots, min_pct_move=0.8)  # 4H ลด threshold เพื่อไม่ให้โล่ง

    lastH = None
    lastL = None
    for p in reversed(pivots):
        if lastH is None and p.get("type") == "H":
            lastH = float(p.get("price"))
        if lastL is None and p.get("type") == "L":
            lastL = float(p.get("price"))
        if lastH is not None and lastL is not None:
            break

    if lastH is None or lastL is None:
        return False, False, "4H pivots not enough"

    confirm_long = close > lastH
    confirm_short = close < lastL
    return confirm_long, confirm_short, f"4H close={close:.2f} lastH={lastH:.2f} lastL={lastL:.2f}"


def get_mtf_summary(
    symbol: str,
    weekly_limit: int = 300,
    h4_limit: int = 800,
) -> Dict:
    """
    1W = permit direction
    4H = confirm entry
    """

    dfw = _prepare_df(symbol, "1w", weekly_limit)
    df4 = _prepare_df(symbol, "4h", h4_limit)

    if dfw is None or len(dfw) < 250:
        s = MTFSummary(
            symbol=symbol,
            weekly_trend="NEUTRAL",
            h4_trend="NEUTRAL",
            weekly_permit_long=True,
            weekly_permit_short=True,
            h4_confirm_long=False,
            h4_confirm_short=False,
            notes="weekly len<250",
        )
        return s.__dict__

    weekly_trend = trend_filter_ema(dfw)
    h4_trend = trend_filter_ema(df4) if (df4 is not None and len(df4) >= 250) else "NEUTRAL"

    # Strict permit: 1W BULL => long only, 1W BEAR => short only, NEUTRAL => both
    weekly_permit_long = True
    weekly_permit_short = True
    if weekly_trend == "BULL":
        weekly_permit_short = False
    elif weekly_trend == "BEAR":
        weekly_permit_long = False

    # 4H confirm
    h4_confirm_long, h4_confirm_short, note4 = _h4_structure_confirm(df4)

    s = MTFSummary(
        symbol=symbol,
        weekly_trend=weekly_trend,
        h4_trend=h4_trend,
        weekly_permit_long=weekly_permit_long,
        weekly_permit_short=weekly_permit_short,
        h4_confirm_long=h4_confirm_long,
        h4_confirm_short=h4_confirm_short,
        notes=note4,
    )
    return s.__dict__
