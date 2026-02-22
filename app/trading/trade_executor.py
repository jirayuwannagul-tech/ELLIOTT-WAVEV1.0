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
    side      = "BUY" if direction == "LONG" else "SELL"

    if get_active(symbol, TIMEFRAME):
        print(f"⚠️ [{symbol}] มี position อยู่แล้ว ไม่เปิดซ้ำ", flush=True)
        return False

    balance  = get_balance()
    quantity = calculate_quantity(balance, RISK_PCT, entry, sl)

    set_margin_type(symbol, "ISOLATED")
    set_leverage(symbol, 10)

    # เปิด order
    order = open_market_order(symbol, side, quantity)
    order_id = order.get("orderId")
    if order_id is None:
        print("❌ ไม่ได้รับ orderId", flush=True)
        return False
    print(f"✅ Order เปิดแล้ว orderId={order_id}", flush=True)

    # ตั้ง SL — ถ้าล้มเหลวให้ cancel order ทันที
    try:
        set_stop_loss(symbol, side, quantity, sl)
        print(f"✅ SL ตั้งแล้ว {sl}", flush=True)
    except Exception as e:
        print(f"❌ SL ล้มเหลว: {e} — ยกเลิก order", flush=True)
        try:
            cancel_order(symbol, int(order_id))
            print(f"✅ cancel order สำเร็จ", flush=True)
        except Exception as ce:
            print(f"❌ cancel ไม่ได้: {ce}", flush=True)
        return False

    # ตั้ง TP
    try:
        set_take_profit(symbol, side, quantity, tp3)
        print(f"✅ TP ตั้งแล้ว {tp3}", flush=True)
    except Exception as e:
        print(f"⚠️ TP ล้มเหลว: {e}", flush=True)

    # ✅ เพิ่มตรงนี้ — บันทึก position ลง DB
    lock_new_position(
        symbol=symbol,
        timeframe=TIMEFRAME,
        direction=direction,
        trade_plan=signal["trade_plan"],
    )
    print(f"✅ [{symbol}] lock position สำเร็จ", flush=True)

    return True  # ← บรรทัดเดิม ไม่ต้องแก้