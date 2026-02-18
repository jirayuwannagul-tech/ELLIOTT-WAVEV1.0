# app/analysis/macro_bias.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class MacroBias:
    bias: str          # "LONG" | "SHORT" | "NEUTRAL"
    strength: float    # 0-100
    allow_long: bool
    allow_short: bool
    notes: str = ""


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(float(x), hi))


def compute_macro_bias(regime: Dict, rsi14: float = 50.0) -> Dict:
    """
    Input:
      - regime: dict จาก detect_market_regime()
      - rsi14: ค่า RSI ล่าสุด (ใช้ยืนยันโมเมนตัมแบบเบา ๆ)

    Output:
      - dict MacroBias พร้อม allow_long/allow_short สำหรับ gate
    """
    rg = (regime or {}).get("regime", "CHOP")
    tr = (regime or {}).get("trend", "NEUTRAL")
    vol = (regime or {}).get("vol", "MID")

    trend_strength = float((regime or {}).get("trend_strength", 0) or 0)
    vol_score = float((regime or {}).get("vol_score", 0) or 0)
    rsi14 = float(rsi14 or 50.0)

    bias = "NEUTRAL"
    strength = 0.0

    # ---- core bias from trend ----
    if rg == "TREND":
        if tr == "BULL":
            bias = "LONG"
            strength = 55.0 + (trend_strength * 0.35)
            if rsi14 >= 55:
                strength += 5.0
        elif tr == "BEAR":
            bias = "SHORT"
            strength = 55.0 + (trend_strength * 0.35)
            if rsi14 <= 45:
                strength += 5.0
        else:
            bias = "NEUTRAL"
            strength = 35.0

    elif rg == "RANGE":
        # range: ไม่ bias แรง ให้ neutral เป็นหลัก
        bias = "NEUTRAL"
        strength = 35.0
        # แต่ถ้า rsi เอียงชัด ก็ให้ bias เบา ๆ
        if rsi14 >= 60:
            bias = "LONG"
            strength = 45.0
        elif rsi14 <= 40:
            bias = "SHORT"
            strength = 45.0

    else:  # CHOP
        bias = "NEUTRAL"
        strength = 25.0
        # chop + vol สูง => ระวังสุด
        if vol == "HIGH":
            strength -= 5.0

    # ---- volatility penalty (กันมั่วใน vol สูง) ----
    # vol_score: LOW 25 / MID 55 / HIGH 80 (จาก market_regime)
    if vol_score >= 75:
        strength -= 8.0
    elif vol_score <= 30:
        strength += 3.0

    strength = _clamp(strength)

    # ---- allow gates ----
    # กติกา: ถ้า bias ชัด (>=60) ให้ “ปิดฝั่งสวน” เลย
    allow_long = True
    allow_short = True

    if bias == "LONG" and strength >= 60:
        allow_short = False
    if bias == "SHORT" and strength >= 60:
        allow_long = False

    mb = MacroBias(
        bias=bias,
        strength=round(strength, 2),
        allow_long=allow_long,
        allow_short=allow_short,
        notes=f"rg={rg} tr={tr} vol={vol} rsi={rsi14:.1f} ts={trend_strength:.1f} vs={vol_score:.1f}",
    )
    return mb.__dict__