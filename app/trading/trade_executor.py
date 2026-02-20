# app/trading/trade_executor.py
# รับ signal แล้วสั่งเทรด
# ยังไม่เปิดใช้งาน

import logging
from app.trading.binance_trader import get_balance, open_market_order, set_stop_loss, set_take_profit
from app.trading.position_sizer import calculate_quantity

logger = logging.getLogger(__name__)

RISK_PCT = 0.02  # เสี่ยง 2% ต่อไม้

# สัดส่วนปิดแต่ละ TP
TP1_PCT = 0.50  # ปิด 50% ที่ TP1
TP2_PCT = 0.30  # ปิด 30% ที่ TP2
TP3_PCT = 0.20  # ปิด 20% ที่ TP3

def execute_signal(signal: dict) -> bool:
    symbol    = signal["symbol"]
    direction = signal["direction"]
    entry     = float(signal["trade_plan"]["entry"])
    sl        = float(signal["trade_plan"]["sl"])
    tp1       = float(signal["trade_plan"]["tp1"])
    tp2       = float(signal["trade_plan"]["tp2"])
    tp3       = float(signal["trade_plan"]["tp3"])
    side      = "BUY" if direction == "LONG" else "SELL"

    balance      = get_balance()
    total_qty    = calculate_quantity(balance, RISK_PCT, entry, sl)

    # แบ่ง quantity ตาม %
    qty_tp1 = round(total_qty * TP1_PCT, 4)
    qty_tp2 = round(total_qty * TP2_PCT, 4)
    qty_tp3 = round(total_qty * TP3_PCT, 4)

    # เปิด order เต็ม
    open_market_order(symbol, side, total_qty)

    # ตั้ง SL เต็ม
    set_stop_loss(symbol, side, total_qty, sl)

    # ตั้ง TP แต่ละส่วน
    set_take_profit(symbol, side, qty_tp1, tp1)  # 50% ปิดที่ TP1
    set_take_profit(symbol, side, qty_tp2, tp2)  # 30% ปิดที่ TP2
    set_take_profit(symbol, side, qty_tp3, tp3)  # 20% ปิดที่ TP3

    return True