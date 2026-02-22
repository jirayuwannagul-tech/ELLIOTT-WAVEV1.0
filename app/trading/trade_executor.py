# app/trading/trade_executor.py
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)
from app.trading.binance_trader import (
    get_balance, open_market_order,
    set_stop_loss, set_take_profit,
    set_leverage, set_margin_type,
    cancel_order
)
from app.trading.position_sizer import calculate_quantity
from app.state.position_manager import lock_new_position, get_active
from app.config.wave_settings import TIMEFRAME

RISK_PCT = 0.05  # 5% ต่อไม้

def execute_signal(signal: dict) -> bool:
    symbol    = signal["symbol"]
    direction = signal["direction"]
    entry     = float(signal["trade_plan"]["entry"])
    sl        = float(signal["trade_plan"]["sl"])
    tp3       = float(signal["trade_plan"]["tp3"])

    open_side = "BUY" if direction == "LONG" else "SELL"
    close_side = "SELL" if open_side == "BUY" else "BUY"   # ✅ เพิ่ม

    if get_active(symbol, TIMEFRAME):
        print(f"⚠️ [{symbol}] มี position อยู่แล้ว ไม่เปิดซ้ำ", flush=True)
        return False

    balance  = get_balance()
    quantity = calculate_quantity(balance, RISK_PCT, entry, sl)

    set_margin_type(symbol, "ISOLATED")
    set_leverage(symbol, 10)

    order = open_market_order(symbol, open_side, quantity)  # ✅ ใช้ open_side
    order_id = order.get("orderId")
    if order_id is None:
        print("❌ ไม่ได้รับ orderId", flush=True)
        return False
    print(f"✅ Order เปิดแล้ว orderId={order_id}", flush=True)

    # ✅ ตั้ง SL ต้องใช้ close_side
    try:
        set_stop_loss(symbol, close_side, quantity, sl)
        print(f"✅ SL ตั้งแล้ว {sl}", flush=True)
    except Exception as e:
        print(f"❌ SL ล้มเหลว: {e}", flush=True)
        return False

    # ✅ ตั้ง TP ต้องใช้ close_side
    try:
        set_take_profit(symbol, close_side, quantity, tp3)
        print(f"✅ TP ตั้งแล้ว {tp3}", flush=True)
    except Exception as e:
        print(f"⚠️ TP ล้มเหลว: {e}", flush=True)

    lock_new_position(
        symbol=symbol,
        timeframe=TIMEFRAME,
        direction=direction,
        trade_plan=signal["trade_plan"],
    )
    print(f"✅ [{symbol}] lock position สำเร็จ", flush=True)

    return True