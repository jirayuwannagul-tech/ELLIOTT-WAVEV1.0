# app/analysis/market_regime.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass
class MarketRegime:
    regime: str              # "TREND" | "RANGE" | "CHOP"
    trend: str               # "BULL" | "BEAR" | "NEUTRAL"
    vol: str                 # "LOW" | "MID" | "HIGH"
    trend_strength: float    # 0-100 (คร่าว ๆ)
    vol_score: float         # 0-100 (คร่าว ๆ)
    notes: str = ""


def _safe_float(x, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v
    except Exception:
        return default


def _pct(a: float, b: float) -> float:
    # percent diff of a vs b, guard b=0
    b = float(b)
    if b == 0:
        return 0.0
    return abs((float(a) - b) / b) * 100.0


def detect_market_regime(
    df: pd.DataFrame,
    ema_fast_col: str = "ema50",
    ema_slow_col: str = "ema200",
    atr_col: str = "atr14",
    rsi_col: str = "rsi14",
) -> Dict:
    """
    ต้องมีคอลัมน์: close, ema50, ema200, atr14, rsi14 (ตาม pipeline ปัจจุบันของคุณ)
    คืน dict ที่เอาไปใช้ gate/score ต่อได้ทันที
    """

    if df is None or len(df) < 250:
        mr = MarketRegime(
            regime="CHOP",
            trend="NEUTRAL",
            vol="MID",
            trend_strength=0.0,
            vol_score=0.0,
            notes="len<250",
        )
        return mr.__dict__

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    close = _safe_float(last.get("close"))
    ema_fast = _safe_float(last.get(ema_fast_col))
    ema_slow = _safe_float(last.get(ema_slow_col))
    atr = _safe_float(last.get(atr_col))
    rsi = _safe_float(last.get(rsi_col), 50.0)

    # -------- Trend direction (macro-ish) ----------
    # ใช้ระยะห่าง EMA + slope คร่าว ๆ
    ema_gap_pct = _pct(ema_fast, ema_slow)  # % ระยะห่างระหว่าง ema50 กับ ema200
    ema_fast_prev = _safe_float(prev.get(ema_fast_col), ema_fast)
    ema_slow_prev = _safe_float(prev.get(ema_slow_col), ema_slow)

    fast_slope = ema_fast - ema_fast_prev
    slow_slope = ema_slow - ema_slow_prev

    trend = "NEUTRAL"
    if ema_fast > ema_slow and fast_slope >= 0:
        trend = "BULL"
    elif ema_fast < ema_slow and fast_slope <= 0:
        trend = "BEAR"

    # -------- Volatility ----------
    # ATR เป็นหน่วยราคา → ทำให้เป็น % ของ close
    atr_pct = (atr / close * 100.0) if close else 0.0

    # แปลงเป็น vol_score 0-100 แบบง่าย (พอใช้ gate)
    # 1% = ต่ำ, 2.5% = กลาง, 4%+ = สูง (ปรับได้ทีหลัง)
    if atr_pct <= 1.2:
        vol = "LOW"
        vol_score = 25.0
    elif atr_pct <= 2.8:
        vol = "MID"
        vol_score = 55.0
    else:
        vol = "HIGH"
        vol_score = 80.0

    # -------- Regime (TREND / RANGE / CHOP) ----------
    # หลักง่าย: ถ้า EMA gap ใหญ่ + slope ไปทางเดียวกัน -> TREND
    # ถ้า gap เล็ก + RSI กลาง ๆ -> RANGE
    # นอกนั้น -> CHOP
    same_slope_dir = (fast_slope >= 0 and slow_slope >= 0) or (fast_slope <= 0 and slow_slope <= 0)

    trend_strength = 0.0
    # strength คร่าว ๆ จาก gap + slope + RSI bias
    trend_strength += min(ema_gap_pct * 10.0, 60.0)  # gap 6% -> +60
    trend_strength += 20.0 if same_slope_dir else 0.0
    if trend == "BULL":
        trend_strength += 10.0 if rsi >= 55 else 0.0
    elif trend == "BEAR":
        trend_strength += 10.0 if rsi <= 45 else 0.0
    trend_strength = max(0.0, min(trend_strength, 100.0))

    regime = "CHOP"
    if ema_gap_pct >= 1.0 and same_slope_dir:
        regime = "TREND"
    elif ema_gap_pct <= 0.5 and 45.0 <= rsi <= 55.0:
        regime = "RANGE"

    mr = MarketRegime(
        regime=regime,
        trend=trend,
        vol=vol,
        trend_strength=round(trend_strength, 2),
        vol_score=round(vol_score, 2),
        notes=f"ema_gap={ema_gap_pct:.2f}% atr%={atr_pct:.2f} rsi={rsi:.1f}",
    )
    return mr.__dict__