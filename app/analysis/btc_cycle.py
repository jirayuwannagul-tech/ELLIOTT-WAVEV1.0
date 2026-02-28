from __future__ import annotations

from typing import List, Dict, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ATR
# ─────────────────────────────────────────────

def _calc_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high  = df["high"]
    low   = df["low"]
    prev  = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev).abs(),
        (low  - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()


# ─────────────────────────────────────────────
# WEEKLY PIVOT
# ─────────────────────────────────────────────

def _find_weekly_pivots(df: pd.DataFrame, atr_mult: float = 2.5) -> List[Dict]:
    """
    หา swing ใหญ่จาก 1W ด้วย ZigZag + ATR filter
    atr_mult สูง = กรอง noise ออก เหลือแค่ Primary Wave swings
    """
    if df is None or len(df) < 20:
        return []

    atr = _calc_atr(df, length=14)
    highs_idx = []
    lows_idx  = []

    for i in range(2, len(df) - 2):
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])

        is_h = all(h >= float(df["high"].iloc[i + k]) for k in [-2, -1, 1, 2])
        is_l = all(l <= float(df["low"].iloc[i + k])  for k in [-2, -1, 1, 2])

        if is_h:
            highs_idx.append(i)
        if is_l:
            lows_idx.append(i)

    # รวม H และ L เรียงตาม index
    raw = []
    for i in highs_idx:
        raw.append({"index": i, "type": "H", "price": float(df["high"].iloc[i]),
                    "ts": df.index[i] if hasattr(df.index[i], 'date') else None})
    for i in lows_idx:
        raw.append({"index": i, "type": "L", "price": float(df["low"].iloc[i]),
                    "ts": df.index[i] if hasattr(df.index[i], 'date') else None})

    raw.sort(key=lambda x: x["index"])

    # ZigZag — สลับ H/L เอา extreme
    zigzag: List[Dict] = []
    for p in raw:
        if not zigzag:
            zigzag.append(p)
            continue
        last = zigzag[-1]
        if p["type"] == last["type"]:
            # เอา extreme
            if p["type"] == "H" and p["price"] > last["price"]:
                zigzag[-1] = p
            elif p["type"] == "L" and p["price"] < last["price"]:
                zigzag[-1] = p
        else:
            # ATR filter — swing ต้องใหญ่พอ
            atr_val = float(atr.iloc[p["index"]]) if p["index"] < len(atr) else 0
            min_move = atr_val * atr_mult
            if abs(p["price"] - last["price"]) >= min_move:
                zigzag.append(p)

    return zigzag


# ─────────────────────────────────────────────
# นับ Primary Wave
# ─────────────────────────────────────────────

def _count_primary_waves(pivots: List[Dict]) -> List[Dict]:
    """
    นับ Primary Wave จาก pivot ที่หาได้
    ใช้ logic ง่ายๆ:
    - impulse swing ใหญ่ = wave 1/3/5
    - correction swing = wave 2/4/A/B/C
    - ดู HH/HL สำหรับ uptrend, LH/LL สำหรับ downtrend
    """
    if len(pivots) < 4:
        return []

    waves = []
    labels = ["1", "2", "3", "4", "5", "A", "B", "C"]
    label_idx = 0

    for i in range(len(pivots) - 1):
        p0 = pivots[i]
        p1 = pivots[i + 1]

        direction = "UP" if p1["price"] > p0["price"] else "DOWN"
        size = abs(p1["price"] - p0["price"])
        pct  = size / p0["price"] * 100

        label = labels[label_idx % len(labels)]
        label_idx += 1

        waves.append({
            "wave":      label,
            "direction": direction,
            "start":     p0,
            "end":       p1,
            "size":      size,
            "pct":       round(pct, 2),
        })

    return waves


# ─────────────────────────────────────────────
# หา Current Wave Position
# ─────────────────────────────────────────────

def _get_current_wave(waves: List[Dict], current_price: float) -> Dict:
    """
    หา wave ที่กำลังอยู่ตอนนี้
    """
    if not waves:
        return {}

    last_wave = waves[-1]
    direction = last_wave["direction"]

    # คำนวณ fib target ของ wave ปัจจุบัน
    start_price = float(last_wave["start"]["price"])
    end_price   = float(last_wave["end"]["price"])
    span        = abs(end_price - start_price)

    fib_targets: Dict = {}
    if direction == "DOWN":
        fib_targets = {
            "0.236": round(end_price + span * 0.236, 0),
            "0.382": round(end_price + span * 0.382, 0),
            "0.5":   round(end_price + span * 0.5,   0),
            "0.618": round(end_price + span * 0.618, 0),
        }
        bias = "BEARISH"
    else:
        fib_targets = {
            "1.0":   round(start_price + span * 1.0,   0),
            "1.618": round(start_price + span * 1.618, 0),
            "2.0":   round(start_price + span * 2.0,   0),
        }
        bias = "BULLISH"

    # คำนวณว่าตอนนี้ retrace ไปแล้วกี่ %
    if direction == "DOWN":
        retrace = (current_price - end_price) / span if span > 0 else 0
    else:
        retrace = (end_price - current_price) / span if span > 0 else 0

    return {
        "wave":        last_wave["wave"],
        "direction":   direction,
        "bias":        bias,
        "wave_high":   max(start_price, end_price),
        "wave_low":    min(start_price, end_price),
        "fib_targets": fib_targets,
        "retrace_pct": round(retrace * 100, 1),
        "note":        f"Primary Wave {last_wave['wave']} ({direction}) — {last_wave['pct']:.1f}% move",
        "all_waves":   waves,
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def analyze_primary_wave(symbol: str, df_1w: Optional[pd.DataFrame] = None) -> Dict:
    """
    วิเคราะห์ Primary Wave จาก 1W data จริงๆ
    ถ้าไม่ได้ส่ง df_1w มา จะดึงจาก Binance เอง
    """
    if df_1w is None or len(df_1w) == 0:
        try:
            from app.data.binance_fetcher import fetch_ohlcv, drop_unclosed_candle
            df_1w = fetch_ohlcv(symbol, interval="1w", limit=500)
            df_1w = drop_unclosed_candle(df_1w)
        except Exception as e:
            logger.error(f"[{symbol}] ดึง 1W ไม่ได้: {e}")
            return {}

    if df_1w is None or len(df_1w) < 20:
        return {}

    current_price = float(df_1w["close"].iloc[-1])

    # หา pivot ใหญ่จาก 1W
    pivots = _find_weekly_pivots(df_1w, atr_mult=2.5)

    if len(pivots) < 4:
        logger.warning(f"[{symbol}] Weekly pivots ไม่พอ ({len(pivots)} จุด)")
        return {}

    # นับ Primary Wave
    waves = _count_primary_waves(pivots)

    # หา current wave
    result = _get_current_wave(waves, current_price)
    result["symbol"]        = symbol
    result["pivot_count"]   = len(pivots)
    result["current_price"] = current_price

    return result


# ─────────────────────────────────────────────
# BACKWARD COMPAT: get_primary_bias สำหรับ BTC
# ─────────────────────────────────────────────

def get_primary_bias(symbol: str = "BTCUSDT") -> Dict:
    """
    wrapper เดิม — ใช้ analyze_primary_wave แทน hardcode
    """
    result = analyze_primary_wave(symbol)

    if not result:
        return {
            "wave": "?", "degree": "Primary",
            "direction": "UNKNOWN", "bias": "NEUTRAL",
            "note": "วิเคราะห์ไม่ได้", "fib_targets": {},
            "wave_high": None, "wave_low": None,
        }

    return {
        "wave":       result.get("wave", "?"),
        "degree":     "Primary",
        "direction":  result.get("direction", "UNKNOWN"),
        "bias":       result.get("bias", "NEUTRAL"),
        "note":       result.get("note", ""),
        "fib_targets": result.get("fib_targets", {}),
        "wave_high":  result.get("wave_high"),
        "wave_low":   result.get("wave_low"),
    }