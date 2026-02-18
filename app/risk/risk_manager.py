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
    direction = scenario["direction"]
    pivots = scenario["pivots"]

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
    # ABC (Wave C projection)
    # Pattern:
    #   ABC_DOWN: H0-L1-H2-L3  (A: H0->L1, B: ->H2, C: project down from H2)
    #   ABC_UP  : L0-H1-L2-H3  (A: L0->H1, B: ->L2, C: project up from L2)
    # =========================
    if stype == "ABC_DOWN":
        # pivots = [H0, L1, H2, L3]
        h0 = float(pivots[0]["price"])
        l1 = float(pivots[1]["price"])
        h2 = float(pivots[2]["price"])

        a_len = abs(h0 - l1)  # ความยาว wave A
        entry = l1            # trigger: ปิดต่ำกว่า L1
        sl = h2               # invalidation: ปิดเหนือ H2

        tp1 = h2 - (a_len * 1.0)
        tp2 = h2 - (a_len * 1.618)
        tp3 = h2 - (a_len * 2.0)

        rr = calculate_rr(entry, sl, tp2)

        if rr >= min_rr:
            trade.update({
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "valid": True,
                "reason": f"RR={round(rr,2)} ≥ {min_rr}",
            })
        else:
            trade["reason"] = f"RR ต่ำ ({round(rr,2)})"

        return trade

    if stype == "ABC_UP":
        # pivots = [L0, H1, L2, H3]
        l0 = float(pivots[0]["price"])
        h1 = float(pivots[1]["price"])
        l2 = float(pivots[2]["price"])

        a_len = abs(h1 - l0)  # ความยาว wave A
        entry = h1            # trigger: ปิดเหนือ H1
        sl = l2               # invalidation: ปิดต่ำกว่า L2

        tp1 = l2 + (a_len * 1.0)
        tp2 = l2 + (a_len * 1.618)
        tp3 = l2 + (a_len * 2.0)

        rr = calculate_rr(entry, sl, tp2)

        if rr >= min_rr:
            trade.update({
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "valid": True,
                "reason": f"RR={round(rr,2)} ≥ {min_rr}",
            })
        else:
            trade["reason"] = f"RR ต่ำ ({round(rr,2)})"

        return trade

    # =========================
    # Impulse (คงแบบเดิมก่อน)
    # =========================
    # ใช้ pivot ล่าสุดเป็น trigger แบบง่าย: breakout = pivot ล่าสุด
    breakout = float(pivots[-1]["price"])
    sl = float(pivots[-2]["price"])
    entry = breakout

    # TP แบบง่าย: ใช้ความยาวช่วงแรกสุดเป็นฐาน
    base_len = abs(float(pivots[1]["price"]) - float(pivots[0]["price"]))

    if direction == "LONG":
        tp1 = entry + base_len * 1.0
        tp2 = entry + base_len * 1.618
        tp3 = entry + base_len * 2.0
    else:
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
            "reason": f"RR={round(rr,2)} ≥ {min_rr}",
        })
    else:
        trade["reason"] = f"RR ต่ำ ({round(rr,2)})"

    return trade