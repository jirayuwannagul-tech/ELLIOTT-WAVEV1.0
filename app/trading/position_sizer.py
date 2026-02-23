# app/trading/position_sizer.py

def calculate_quantity(balance: float, risk_pct: float, entry: float, sl: float) -> float:
    """
    balance  = เงินในพอร์ต (USDT)
    risk_pct = % เสี่ยงต่อไม้ เช่น 0.5% = 0.005
    entry    = ราคาเข้า
    sl       = stop loss
    return   = จำนวนเหรียญ (qty)
    """

    risk_amount = balance * risk_pct
    sl_distance = abs(entry - sl)

    if sl_distance <= 0:
        return 0.0

    qty = risk_amount / sl_distance
    return round(qty, 6)