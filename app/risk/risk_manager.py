from __future__ import annotations

from typing import Dict


def calculate_rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return 0
    return reward / risk


def build_trade_plan(scenario: Dict, current_price: float, min_rr: float = 2.0) -> Dict:
    """
    Build entry / SL / TP based on scenario
    Close-confirm style:
      - Entry = breakout trigger level (ยังไม่ถือว่าเข้า จนกว่าจะปิดแท่งยืนยัน)
    """

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
    # ✅ FIX: กัน KeyError เมื่อ scenario ไม่มี pivots
    #    ใช้ range_low/range_high/atr ที่ผ่านมาใน scenario dict
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
            entry = current_price
            sl    = range_low - atr * 0.5          # ใต้ support + buffer ATR
            tp1   = range_low + span * 0.382
            tp2   = range_low + span * 0.618
            tp3   = range_high - atr * 0.3          # ใกล้ resist แต่ไม่ชน

        elif direction == "SHORT":
            entry = current_price
            sl    = range_high + atr * 0.5          # เหนือ resist + buffer ATR
            tp1   = range_high - span * 0.382
            tp2   = range_high - span * 0.618
            tp3   = range_low + atr * 0.3           # ใกล้ support แต่ไม่ชน

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
    # Pattern:
    #   ABC_DOWN : H0-L1-H2-L3  → SHORT เมื่อปิดต่ำกว่า L1
    #   ABC_UP   : L0-H1-L2-H3  → LONG เมื่อปิดเหนือ H1
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

        a_len = abs(h0 - l1)   # ความยาว wave A
        entry = l1              # trigger: ปิดต่ำกว่า L1
        sl    = h2              # invalidation: ปิดเหนือ H2

        # ✅ FIX: project TP จาก entry (l1) ไม่ใช่ h2
        # เดิม project จาก h2 ทำให้ tp1 อาจอยู่เหนือ entry ได้เมื่อ B retrace ลึก
        tp1 = entry - (a_len * 1.0)
        tp2 = entry - (a_len * 1.618)
        tp3 = entry - (a_len * 2.0)

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

    if stype == "ABC_UP":
        l0 = float(pivots[0]["price"])
        h1 = float(pivots[1]["price"])
        l2 = float(pivots[2]["price"])

        a_len = abs(h1 - l0)   # ความยาว wave A
        entry = h1              # trigger: ปิดเหนือ H1
        sl    = l2              # invalidation: ปิดต่ำกว่า L2

        # ✅ FIX: project TP จาก entry (h1) ไม่ใช่ l2
        # เดิม project จาก l2 ทำให้ tp1 อาจอยู่ใต้ entry ได้เมื่อ B retrace ตื้น
        tp1 = entry + (a_len * 1.0)
        tp2 = entry + (a_len * 1.618)
        tp3 = entry + (a_len * 2.0)

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
    # Impulse (LONG / SHORT)
    # ใช้ pivot ล่าสุดเป็น breakout trigger
    # =========================
    pivots = scenario.get("pivots") or []
    if len(pivots) < 2:
        trade["reason"] = "IMPULSE: pivots ไม่พอ"
        return trade

    breakout = float(pivots[-1]["price"])
    sl       = float(pivots[-2]["price"])
    entry    = breakout

    # TP ใช้ความยาวช่วงแรกสุดเป็นฐาน
    base_len = abs(float(pivots[1]["price"]) - float(pivots[0]["price"]))

    if direction == "LONG":
        tp1 = entry + base_len * 1.0
        tp2 = entry + base_len * 1.618
        tp3 = entry + base_len * 2.0
    else:  # SHORT
        tp1 = entry - base_len * 1.0
        tp2 = entry - base_len * 1.618
        tp3 = entry - base_len * 2.0

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