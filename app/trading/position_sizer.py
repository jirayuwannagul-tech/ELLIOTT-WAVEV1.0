# app/trading/position_sizer.py
# คำนวณขนาด position จากงบและ risk %

def calculate_quantity(balance: float, risk_pct: float, entry: float, sl: float) -> float:
    """
    balance  = ยอดเงินใน wallet (USDT)
    risk_pct = % ที่ยอมเสียต่อไม้ เช่น 0.02 = 2%
    entry    = ราคาเข้า
    sl       = stop loss
    return   = จำนวน coin ที่ซื้อ
    """
    risk_amount = balance * risk_pct
    sl_distance = abs(entry - sl)
    if sl_distance <= 0:
        return 0.0
    return round(risk_amount / sl_distance, 3)
