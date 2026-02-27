from __future__ import annotations

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# SL ต้องห่างจาก entry อย่างน้อยกี่ % ถึงจะ valid
# ถ้าน้อยกว่านี้ = SL ใกล้เกินไป โดนง่ายมาก → reject
MIN_SL_PCT = 2.0
MAX_SL_PCT = 8.0

def calculate_rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return 0.0
    return reward / risk


def _safe_fib_extension(
    p0: float,
    p1: float,
    anchor: float,
    direction: str,
    base_len: float,
) -> Optional[Dict]:
    direction = (direction or "").upper()

    if base_len <= 0:
        base_len = abs(p1 - p0)
    if base_len <= 0:
        logger.warning(f"fib_extension: base_len<=0 (p0={p0}, p1={p1}) -> return None")
        return None

    if direction == "LONG":
        t1 = anchor + base_len * 1.0
        t2 = anchor + base_len * 1.618
        t3 = anchor + base_len * 2.0
    else:  # SHORT
        t1 = anchor - base_len * 1.0
        t2 = anchor - base_len * 1.618
        t3 = anchor - base_len * 2.0

    if t1 <= 0 or t2 <= 0 or t3 <= 0:
        logger.warning(
            f"fib_extension: invalid targets (t1={t1:.6f}, t2={t2:.6f}, t3={t3:.6f}) "
            f"anchor={anchor}, base_len={base_len} -> return None"
        )
        return None

    return {"1.0": t1, "1.618": t2, "2.0": t3}


def _check_sl_distance(entry: float, sl: float, direction: str) -> Optional[str]:
    if entry <= 0:
        return "entry <= 0"
    sl_pct = abs(entry - sl) / entry * 100
    if sl_pct < MIN_SL_PCT:
        return f"SL ใกล้เกินไป ({sl_pct:.2f}% < {MIN_SL_PCT}%)"
    if sl_pct > MAX_SL_PCT:
        return f"SL ไกลเกินไป ({sl_pct:.2f}% > {MAX_SL_PCT}%)"
    return None


def _cap_tp3_by_max_r(entry: float, sl: float, tp3: float, direction: str) -> float:
    """
    จำกัด TP3 ไม่ให้เกิน MAX_TP_R (หน่วยเป็น R)
    เปิดใช้ด้วย env: MAX_TP_R=3 (หรือ 2.5, 4 ฯลฯ)

    หมายเหตุ:
    - ไม่แตะ tp1/tp2
    - ใช้ risk จาก |entry-sl| หลังปรับ sr แล้วเท่านั้น
    """
    try:
        s = (os.getenv("MAX_TP_R", "") or "").strip()
        max_r = float(s) if s else 0.0
    except Exception:
        max_r = 0.0

    if not max_r or max_r <= 0:
        return float(tp3)

    risk = abs(float(entry) - float(sl))
    if risk <= 0:
        return float(tp3)

    d = (direction or "").upper()
    if d == "LONG":
        r_tp3 = (float(tp3) - float(entry)) / risk
        if r_tp3 > max_r:
            return float(entry) + risk * max_r
        return float(tp3)

    if d == "SHORT":
        r_tp3 = (float(entry) - float(tp3)) / risk
        if r_tp3 > max_r:
            return float(entry) - risk * max_r
        return float(tp3)

    return float(tp3)


def build_trade_plan(
    scenario: Dict,
    current_price: float,
    min_rr: float = 2.0,
    sr: Optional[Dict] = None,
) -> Dict:
    stype = (scenario.get("type") or "").upper()
    direction = (scenario.get("direction") or "").upper()

    trade = {
        "direction": direction,
        "entry": None,
        "sl": None,
        "tp1": None,
        "tp2": None,
        "tp3": None,
        "valid": False,
        "reason": "",
    }

    # =========================
    # SIDEWAY_RANGE
    # =========================
    if stype == "SIDEWAY_RANGE":
        range_low = float(scenario.get("range_low") or 0)
        range_high = float(scenario.get("range_high") or 0)
        atr = float(scenario.get("atr") or current_price * 0.01)

        if range_low <= 0 or range_high <= range_low:
            trade["reason"] = "SIDEWAY: range ไม่ valid"
            return trade

        span = range_high - range_low

        if direction == "LONG":
            entry = float(current_price)
            sl = range_low - atr * 0.5
            tp1 = range_low + span * 0.382
            tp2 = range_low + span * 0.618
            tp3 = range_high - atr * 0.3
        elif direction == "SHORT":
            entry = float(current_price)
            sl = range_high + atr * 0.5
            tp1 = range_high - span * 0.382
            tp2 = range_high - span * 0.618
            tp3 = range_low + atr * 0.3
        else:
            trade["reason"] = "SIDEWAY: direction ไม่ถูกต้อง"
            return trade

        # SL distance check
        sl_err = _check_sl_distance(entry, sl, direction)
        if sl_err:
            trade["reason"] = f"SIDEWAY: {sl_err}"
            return trade

        # ✅ APPLY CAP (ให้ MAX_TP_R มีผลจริง)
        tp3 = _cap_tp3_by_max_r(entry, sl, tp3, direction)

        rr = calculate_rr(entry, sl, tp2)
        if rr >= min_rr:
            trade.update({
                "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "valid": True,
                "reason": f"RR(TP2)={round(rr, 2)} ≥ {min_rr}",
            })
        else:
            trade["reason"] = f"RR(TP2) ต่ำ ({round(rr, 2)})"
        return trade

    # =========================
    # ABC
    # =========================
    if stype in ("ABC_DOWN", "ABC_UP"):
        pivots = scenario.get("pivots") or []
        if len(pivots) < 3:
            trade["reason"] = "ABC: pivots ไม่พอ"
            return trade

        if stype == "ABC_DOWN":
            h0 = float(pivots[0]["price"])
            l1 = float(pivots[1]["price"])
            h2 = float(pivots[2]["price"])
            a_len = abs(h0 - l1)

            if current_price >= h2:
                trade["reason"] = "ABC_DOWN: ราคาเหนือ SL แล้ว (invalid)"
                return trade

            entry = float(current_price)
            sl = h2

            # SL distance check
            sl_err = _check_sl_distance(entry, sl, direction)
            if sl_err:
                trade["reason"] = f"ABC_DOWN: {sl_err}"
                return trade

            fib = _safe_fib_extension(h0, l1, entry, "SHORT", a_len)
            if fib is None:
                trade["reason"] = "fib_invalid: targets<=0 (base_len>anchor)"
                return trade
            tp1, tp2, tp3 = fib["1.0"], fib["1.618"], fib["2.0"]

            # sr adjustment
            if sr:
                resist = (sr.get("resist") or {}).get("level")
                if resist and float(resist) < sl:
                    sl = float(resist)

            # re-check SL distance AFTER sr adjustment
            sl_err = _check_sl_distance(entry, sl, direction)
            if sl_err:
                trade["reason"] = f"ABC_DOWN(after SR): {sl_err}"
                return trade                   

        else:  # ABC_UP
            l0 = float(pivots[0]["price"])
            h1 = float(pivots[1]["price"])
            l2 = float(pivots[2]["price"])
            a_len = abs(h1 - l0)

            if current_price <= l2:
                trade["reason"] = "ABC_UP: ราคาต่ำกว่า SL แล้ว (invalid)"
                return trade

            entry = float(current_price)
            sl = l2

            # SL distance check — ก่อน SR
            sl_err = _check_sl_distance(entry, sl, direction)
            if sl_err:
                trade["reason"] = f"ABC_UP: {sl_err}"
                return trade

            fib = _safe_fib_extension(l0, h1, entry, "LONG", a_len)
            if fib is None:
                trade["reason"] = "fib_invalid: targets<=0 (base_len>anchor)"
                return trade
            tp1, tp2, tp3 = fib["1.0"], fib["1.618"], fib["2.0"]

            # SR adjustment
            if sr:
                support = (sr.get("support") or {}).get("level")
                if support and float(support) > sl:
                    sl = float(support)

            # ✅ re-check SL distance — หลัง SR
            sl_err = _check_sl_distance(entry, sl, direction)
            if sl_err:
                trade["reason"] = f"ABC_UP(after SR): {sl_err}"
                return trade

        # cap TP3 หลัง SR (เหมือนเดิม)
        tp3 = _cap_tp3_by_max_r(entry, sl, tp3, direction)

        # ✅ RR gate ให้ตรงกับ execution: ใช้ TP2
        rr = calculate_rr(entry, sl, tp2)

        if rr >= min_rr:
            trade.update({
                "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "valid": True,
                "reason": f"RR(TP2)={round(rr, 2)} ≥ {min_rr} (fib+sr)",
            })
        else:
            trade["reason"] = f"RR(TP2) ต่ำ ({round(rr, 2)})"
        return trade
    # =========================
    # IMPULSE
    # =========================
    pivots = scenario.get("pivots") or []
    if len(pivots) < 2:
        trade["reason"] = "IMPULSE: pivots ไม่พอ"
        return trade

    breakout = float(pivots[-1]["price"])
    sl = float(pivots[-2]["price"])
    entry = breakout
    p0 = float(pivots[0]["price"])
    p1 = float(pivots[1]["price"])
    base_len = abs(p1 - p0)

    # SL distance check
    sl_err = _check_sl_distance(entry, sl, direction)
    if sl_err:
        trade["reason"] = f"IMPULSE: {sl_err}"
        return trade

    fib = _safe_fib_extension(p0, p1, entry, direction, base_len)
    if fib is None:
        trade["reason"] = "fib_invalid: targets<=0 (base_len>anchor)"
        return trade
    tp1, tp2, tp3 = fib["1.0"], fib["1.618"], fib["2.0"]

    # sr adjustment
    if direction == "LONG":
        if sr:
            support = (sr.get("support") or {}).get("level")
            if support and float(support) > sl:
                sl = float(support)
    elif direction == "SHORT":
        if sr:
            resist = (sr.get("resist") or {}).get("level")
            if resist and float(resist) < sl:
                sl = float(resist)
    else:
        trade["reason"] = "IMPULSE: direction ไม่ถูกต้อง"
        return trade

    # re-check SL distance AFTER sr adjustment
    sl_err = _check_sl_distance(entry, sl, direction)
    if sl_err:
        trade["reason"] = f"IMPULSE(after SR): {sl_err}"
        return trade

    # ✅ APPLY CAP หลัง sr adjustment เสร็จ (สำคัญ)
    tp3 = _cap_tp3_by_max_r(entry, sl, tp3, direction)

    rr = calculate_rr(entry, sl, tp2)
    if rr >= min_rr:
        trade.update({
            "entry": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "valid": True,
            "reason": f"RR(TP2)={round(rr, 2)} ≥ {min_rr} (fib+sr)",
        })
    else:
        trade["reason"] = f"RR(TP2) ต่ำ ({round(rr, 2)})"

    return trade


def recalculate_from_fill(
    direction: str,
    actual_entry: float,
    original_sl: float,
    original_tp_rr: float,
    min_rr: float = 1.6,
) -> Dict:
    direction = direction.upper()
    risk = abs(actual_entry - original_sl)

    if risk <= 0:
        return {"valid": False, "reason": "risk=0 (entry==sl)"}

    if direction == "LONG":
        tp1 = actual_entry + risk * 1.0
        tp2 = actual_entry + risk * original_tp_rr
        tp3 = actual_entry + risk * 2.0
    else:
        tp1 = actual_entry - risk * 1.0
        tp2 = actual_entry - risk * original_tp_rr
        tp3 = actual_entry - risk * 2.0

    rr = calculate_rr(actual_entry, original_sl, tp2)

    if rr < min_rr:
        return {
            "valid": False,
            "reason": f"RR(TP2) หลัง fill ต่ำ ({round(rr,2)} < {min_rr})",
            "actual_entry": actual_entry,
            "sl": original_sl,
            "rr": round(rr, 2),
        }

    return {
        "valid": True,
        "actual_entry": actual_entry,
        "sl": original_sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rr": round(rr, 2),
        "risk": round(risk, 6),
    }