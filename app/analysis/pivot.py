from __future__ import annotations

import pandas as pd
import numpy as np
from typing import List, Dict, Optional


def _calc_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """คำนวณ ATR แบบ simple สำหรับใช้ใน pivot detection"""
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()


def find_fractal_pivots(
    df: pd.DataFrame,
    atr_mult: float = 1.5,
    atr_length: int = 14,
    left: int = 2,
    right: int = 2,
) -> List[Dict]:
    """
    ZigZag-based pivot detection กรองด้วย ATR
    
    แทนที่ fractal 2-2 แบบเดิม — ตอนนี้ต้องการให้ swing มีระยะ
    อย่างน้อย atr_mult * ATR ถึงจะนับเป็น pivot ที่มีนัยสำคัญ
    
    Returns list of dict:
    {
        "index": int,
        "price": float,
        "type": "H" or "L",
        "degree": "minor" or "intermediate"
        "atr_at_pivot": float,
    }
    """
    # ✅ แบบใหม่
    if df is None or len(df) < left + right + 1:
        return []

    atr_series = _calc_atr(df, length=atr_length)

    # --- Step 1: หา fractal pivot เบื้องต้น (เหมือนเดิม) ---
    raw_pivots: List[Dict] = []

    for i in range(left, len(df) - right):
        high_slice = df["high"].iloc[i - left: i + right + 1]
        low_slice  = df["low"].iloc[i - left: i + right + 1]

        current_high = float(df["high"].iloc[i])
        current_low  = float(df["low"].iloc[i])
        atr_val      = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else 0.0

        is_pivot_high = (current_high == high_slice.max())
        is_pivot_low  = (current_low  == low_slice.min())

        # กัน H+L บนแท่งเดียวกัน
        if is_pivot_high and is_pivot_low:
            prev_close = float(df["close"].iloc[i - 1])
            if abs(current_high - prev_close) >= abs(current_low - prev_close):
                is_pivot_low = False
            else:
                is_pivot_high = False

        if is_pivot_high:
            raw_pivots.append({
                "index": i,
                "price": current_high,
                "type": "H",
                "atr_at_pivot": atr_val,
            })
        elif is_pivot_low:
            raw_pivots.append({
                "index": i,
                "price": current_low,
                "type": "L",
                "atr_at_pivot": atr_val,
            })

    if not raw_pivots:
        return []

    # --- Step 2: ZigZag filter — สลับ H/L จริงๆ ---
    # เก็บเฉพาะ pivot ที่ต่างประเภทกับตัวก่อนหน้า
    # ถ้าประเภทเดิม → เก็บตัวที่ extreme กว่า
    zigzag: List[Dict] = [raw_pivots[0]]

    for pv in raw_pivots[1:]:
        last = zigzag[-1]

        if pv["type"] == last["type"]:
            # ประเภทเดิม → เอาตัวที่ extreme กว่า
            if pv["type"] == "H" and pv["price"] > last["price"]:
                zigzag[-1] = pv
            elif pv["type"] == "L" and pv["price"] < last["price"]:
                zigzag[-1] = pv
        else:
            zigzag.append(pv)

    # --- Step 3: ATR filter — swing ต้องใหญ่พอ ---
    # ระยะจาก pivot ก่อนหน้า >= atr_mult * ATR
    filtered: List[Dict] = []

    for i, pv in enumerate(zigzag):
        if i == 0:
            filtered.append(pv)
            continue

        prev = filtered[-1]
        swing_size = abs(pv["price"] - prev["price"])
        min_swing  = atr_mult * pv["atr_at_pivot"] if pv["atr_at_pivot"] > 0 else 0

        if swing_size >= min_swing:
            filtered.append(pv)
        else:
            # swing เล็กเกินไป → merge กับ prev (เอา extreme กว่า)
            if pv["type"] == "H" and pv["price"] > prev["price"]:
                filtered[-1] = pv
            elif pv["type"] == "L" and pv["price"] < prev["price"]:
                filtered[-1] = pv

    # --- Step 4: กำหนด degree ของ pivot ---
    # intermediate = swing ที่ใหญ่กว่า median ของทุก swing
    # minor = swing ที่เล็กกว่า median
    if len(filtered) >= 2:
        swings = [
            abs(filtered[i]["price"] - filtered[i-1]["price"])
            for i in range(1, len(filtered))
        ]
        median_swing = float(np.median(swings)) if swings else 0.0

        for i, pv in enumerate(filtered):
            if i == 0:
                pv["degree"] = "minor"
                continue
            swing = abs(pv["price"] - filtered[i-1]["price"])
            pv["degree"] = "intermediate" if swing >= median_swing else "minor"
    else:
        for pv in filtered:
            pv["degree"] = "minor"

    return filtered


def filter_pivots(pivots: List[Dict], min_pct_move: float = 1.5) -> List[Dict]:
    """
    กรอง pivot ที่เคลื่อนที่น้อยเกินไปออก
    เพิ่ม min_pct_move default จาก 0.5 → 1.5 
    เพราะ BTC ต้องการ swing ที่มีนัยสำคัญจริงๆ
    """
    if not pivots:
        return []

    filtered = [pivots[0]]

    for pivot in pivots[1:]:
        last = filtered[-1]
        move_pct = abs((pivot["price"] - last["price"]) / last["price"]) * 100

        if move_pct >= min_pct_move:
            filtered.append(pivot)
        else:
            # เล็กเกินไป → merge เอา extreme กว่า
            if pivot["type"] == "H" and pivot["price"] > last["price"]:
                filtered[-1] = pivot
            elif pivot["type"] == "L" and pivot["price"] < last["price"]:
                filtered[-1] = pivot

    return filtered