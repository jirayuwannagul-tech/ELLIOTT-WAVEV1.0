# app/trading/trade_executor.py

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

from app.trading.binance_trader import (
    get_balance,
    open_market_order,
    set_stop_loss,
    set_take_profit,
    set_leverage,
    set_margin_type,
)

from app.trading.position_sizer import calculate_quantity
from app.state.position_manager import lock_new_position, get_active
from app.config.wave_settings import TIMEFRAME

RISK_PCT = 0.05   # เสี่ยง 5% ต่อไม้


def execute_signal(signal: dict) -> bool:
    symbol    = signal["symbol"]
    direction = signal["direction"]
    entry     = float(signal["trade_plan"]["entry"])
    sl        = float(signal["trade_plan"]["sl"])
    tp3       = float(signal["trade_plan"]["tp3"])

    open_side  = "BUY" if direction == "LONG" else "SELL"
    close_side = "SELL" if open_side == "BUY" else "BUY"

    # กันเปิดซ้ำ
    if get_active(symbol, TIMEFRAME):
        print(f"⚠️ [{symbol}] มี position อยู่แล้ว")
        return False

    balance  = get_balance()
    quantity = calculate_quantity(balance, RISK_PCT, entry, sl)

    set_margin_type(symbol, "ISOLATED")
    set_leverage(symbol, 10)

    order = open_market_order(symbol, open_side, quantity)
    order_id = order.get("orderId")

    if not order_id:
        print("❌ เปิดออเดอร์ไม่สำเร็จ")
        return False

    print(f"✅ เปิดออเดอร์แล้ว {symbol} {direction}")

    # SL
    set_stop_loss(symbol, open_side, quantity, sl)
    print(f"✅ SL = {sl}")

    # TP
    set_take_profit(symbol, open_side, quantity, tp3)
    print(f"✅ TP = {tp3}")

    lock_new_position(
        symbol=symbol,
        timeframe=TIMEFRAME,
        direction=direction,
        trade_plan=signal["trade_plan"],
    )

    return True