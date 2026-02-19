from __future__ import annotations

import logging
from typing import Dict, Optional

from app.analysis.fib import fib_extension

logger = logging.getLogger(__name__)


def calculate_rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return 0.0
    return reward / risk


def _safe_fib_extension(p0: float, p1: float, anchor: float, direction: str, base_len: float) -> Dict:
    """
    คำนวณ fib_extension แบบปลอดภัย
    ถ้า p0 == p1 หรือผลออกมาผิดทิศ → fallback คำนวณจาก base_len แทน
    """
    try:
        if abs(p1 - p0) > 0:
            targets = fib_extension(p0, p1, anchor)
            t1 = float(targets["1.0"])
            t2 = float(targets["1.618"])
            t3 = float(targets["2.0"])

            # ตรวจสอบว่า TP ถูกทิศไหม
            if direction == "LONG" and t1 > anchor and t2 > t1 and t3 > t2:
                return {"1.0": t1, "1.618": t2, "2.0": t3}
            if direction == "SHORT" and t1 < anchor and t2 < t1 and t3 < t2:
                return {"1.0": t1, "1.618": t2, "2.0": t3}

            logger.warning(f"fib_extension ผิดทิศ direction={direction} t1={t1} anchor={anchor} → fallback")

    except Exception as e:
        logger.warning(f"fib_extension error: {e} → fallback")

    # fallback: คำนวณจาก base_len
    if direction == "LONG":
        return {
            "1.0": anchor + base_len * 1.0,
            "1.618": anchor + base_len * 1.618,
            "2.0": anchor + base_len * 2.0,
        }
    return {
        "1.0": anchor - base_len * 1.0,
        "1.618": anchor - base_len * 1.618,
        "2.0": anchor - base_len * 2.0,
    }


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

        rr = calculate_rr(entry, sl, tp2)
        if rr >= min_rr:
            trade.update({
                "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "valid": True,
                "reason": f"RR={round(rr, 2)} ≥ {min_rr}",
            })
        else:
            trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"
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

            fib = _safe_fib_extension(h0, l1, entry, "SHORT", a_len)
            tp1, tp2, tp3 = fib["1.0"], fib["1.618"], fib["2.0"]

            if sr:
                resist = (sr.get("resist") or {}).get("level")
                if resist and float(resist) < sl:
                    sl = float(resist)

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

            fib = _safe_fib_extension(l0, h1, entry, "LONG", a_len)
            tp1, tp2, tp3 = fib["1.0"], fib["1.618"], fib["2.0"]

            if sr:
                support = (sr.get("support") or {}).get("level")
                if support and float(support) > sl:
                    sl = float(support)

        rr = calculate_rr(entry, sl, tp2)
        if rr >= min_rr:
            trade.update({
                "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "valid": True,
                "reason": f"RR={round(rr, 2)} ≥ {min_rr} (fib+sr)",
            })
        else:
            trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"
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

    fib = _safe_fib_extension(p0, p1, entry, direction, base_len)
    tp1, tp2, tp3 = fib["1.0"], fib["1.618"], fib["2.0"]

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

    rr = calculate_rr(entry, sl, tp2)
    if rr >= min_rr:
        trade.update({
            "entry": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "valid": True,
            "reason": f"RR={round(rr, 2)} ≥ {min_rr} (fib+sr)",
        })
    else:
        trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"

    return trade
