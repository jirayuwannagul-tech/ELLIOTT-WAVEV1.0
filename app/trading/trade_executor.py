# app/trading/trade_executor.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

from app.trading.binance_trader import (
    get_balance, open_market_order,
    set_stop_loss, set_take_profit,
    set_leverage, set_margin_type
)
from app.trading.position_sizer import calculate_quantity

RISK_PCT = 0.05  # 5% ต่อไม้

def execute_signal(signal: dict) -> bool:

    symbol    = signal["symbol"]
    direction = signal["direction"]
    entry     = float(signal["trade_plan"]["entry"])
    sl        = float(signal["trade_plan"]["sl"])
    tp1       = float(signal["trade_plan"]["tp1"])
    tp2       = float(signal["trade_plan"]["tp2"])
    tp3       = float(signal["trade_plan"]["tp3"])
    side      = "BUY" if direction == "LONG" else "SELL"

    # ดูยอดเงินปัจจุบัน
    balance  = get_balance()

    # คำนวณ qty จาก 5% ของทุน
    quantity = calculate_quantity(balance, RISK_PCT, entry, sl)

    # ตั้งค่า Futures
    set_margin_type(symbol, "ISOLATED")
    set_leverage(symbol, 10)

    # เปิด order
    open_market_order(symbol, side, quantity)

    # ตั้ง SL/TP
    set_stop_loss(symbol, side, quantity, sl)
    set_take_profit(symbol, side, quantity, tp3)

    return True
