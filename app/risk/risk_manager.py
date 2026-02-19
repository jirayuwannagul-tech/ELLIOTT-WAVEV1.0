from __future__ import annotations

from typing import Dict, Optional

from app.analysis.fib import fib_extension


def calculate_rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return 0.0
    return reward / risk


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
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "valid": True,
                "reason": f"RR={round(rr, 2)} ≥ {min_rr}",
            })
        else:
            trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"
        return trade

    # =========================
    # ABC (Wave C projection)
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
            entry = l1
            sl = h2

            # ใช้ fib_extension คำนวณ target จริง
            fib_targets = fib_extension(h0, l1, h2)
            tp1 = fib_targets["1.0"]
            tp2 = fib_targets["1.618"]
            tp3 = fib_targets["2.0"]

            # ถ้ามี sr resist ใกล้กว่า sl -> ปรับ sl ให้แน่นขึ้น
            if sr:
                resist = (sr.get("resist") or {}).get("level")
                if resist and float(resist) < sl:
                    sl = float(resist)

            rr = calculate_rr(entry, sl, tp2)
            if rr >= min_rr:
                trade.update({
                    "entry": entry,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "valid": True,
                    "reason": f"RR={round(rr, 2)} ≥ {min_rr} (fib+sr)",
                })
            else:
                trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"
            return trade

        # ABC_UP
        l0 = float(pivots[0]["price"])
        h1 = float(pivots[1]["price"])
        l2 = float(pivots[2]["price"])

        a_len = abs(h1 - l0)
        entry = h1
        sl = l2

        # ใช้ fib_extension คำนวณ target จริง
        fib_targets = fib_extension(l0, h1, l2)
        tp1 = fib_targets["1.0"]
        tp2 = fib_targets["1.618"]
        tp3 = fib_targets["2.0"]

        # ถ้ามี sr support ใกล้กว่า sl -> ปรับ sl ให้แน่นขึ้น
        if sr:
            support = (sr.get("support") or {}).get("level")
            if support and float(support) > sl:
                sl = float(support)

        rr = calculate_rr(entry, sl, tp2)
        if rr >= min_rr:
            trade.update({
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "valid": True,
                "reason": f"RR={round(rr, 2)} ≥ {min_rr} (fib+sr)",
            })
        else:
            trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"
        return trade

    # =========================
    # IMPULSE (LONG / SHORT)
    # =========================
    pivots = scenario.get("pivots") or []
    if len(pivots) < 2:
        trade["reason"] = "IMPULSE: pivots ไม่พอ"
        return trade

    breakout = float(pivots[-1]["price"])
    sl = float(pivots[-2]["price"])
    entry = breakout

    # ใช้ fib_extension คำนวณ TP จาก wave 1 (p0->p1) ต่อจาก entry
    p0 = float(pivots[0]["price"])
    p1 = float(pivots[1]["price"])
    fib_targets = fib_extension(p0, p1, entry)

    if direction == "LONG":
        tp1 = fib_targets["1.0"]
        tp2 = fib_targets["1.618"]
        tp3 = fib_targets["2.0"]

        # ปรับ SL โดยใช้ sr support ถ้าอยู่เหนือ sl เดิม (แน่นขึ้น)
        if sr:
            support = (sr.get("support") or {}).get("level")
            if support and float(support) > sl:
                sl = float(support)

    elif direction == "SHORT":
        tp1 = fib_targets["1.0"]
        tp2 = fib_targets["1.618"]
        tp3 = fib_targets["2.0"]

        # SHORT: fib_extension ออกทางลง ต้องกลับทิศ
        base_len = abs(p1 - p0)
        tp1 = entry - base_len * 1.0
        tp2 = entry - base_len * 1.618
        tp3 = entry - base_len * 2.0

        # ปรับ SL โดยใช้ sr resist ถ้าอยู่ต่ำกว่า sl เดิม (แน่นขึ้น)
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
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "valid": True,
            "reason": f"RR={round(rr, 2)} ≥ {min_rr} (fib+sr)",
        })
    else:
        trade["reason"] = f"RR ต่ำ ({round(rr, 2)})"

    return trade
