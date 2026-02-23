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

RISK_PCT = 0.05        # เสี่ยง 5% ต่อไม้
MIN_RR_AFTER_FILL = 1.6  # RR ขั้นต่ำหลัง fill จริง


def _get_actual_entry(order: dict, entry_est: float) -> float:
    """
    ดึง fill price จริงจาก order response
    ลำดับ: avgPrice → fills[] weighted avg → entry_est (fallback)
    """
    # 1) avgPrice ตรง ๆ
    avg = float(order.get("avgPrice") or 0)
    if avg > 0:
        return avg

    # 2) weighted avg จาก fills[]
    fills = order.get("fills") or []
    if fills:
        total_qty = sum(float(f["qty"]) for f in fills)
        if total_qty > 0:
            return sum(float(f["price"]) * float(f["qty"]) for f in fills) / total_qty

    # 3) fallback
    return entry_est


def _recalculate_plan(
    direction: str,
    actual_entry: float,
    sl: float,
    tp_rr: float,
) -> dict:
    """
    คำนวณ SL/TP ใหม่จาก actual_entry
    - SL คงเป็น technical level เดิม (ไม่ขยับ)
    - TP recalculate จาก actual_entry × tp_rr ratio เดิม
    """
    direction = direction.upper()
    risk = abs(actual_entry - sl)

    if risk <= 0:
        return {"valid": False, "reason": "risk=0 (entry==sl)"}

    rr = abs(tp_rr)  # กัน negative

    if direction == "LONG":
        tp1 = actual_entry + risk * 1.0
        tp2 = actual_entry + risk * rr
        tp3 = actual_entry + risk * 2.0
    else:
        tp1 = actual_entry - risk * 1.0
        tp2 = actual_entry - risk * rr
        tp3 = actual_entry - risk * 2.0

    actual_rr = abs(tp2 - actual_entry) / risk

    return {
        "valid": True,
        "entry": actual_entry,
        "sl":    sl,
        "tp1":   tp1,
        "tp2":   tp2,
        "tp3":   tp3,
        "rr":    round(actual_rr, 2),
        "risk":  round(risk, 6),
    }


def execute_signal(signal: dict) -> bool:
    symbol     = signal["symbol"]
    direction  = signal["direction"]
    trade_plan = signal["trade_plan"]

    entry_est = float(trade_plan["entry"])
    sl_orig   = float(trade_plan["sl"])
    tp2_orig  = float(trade_plan["tp2"])

    open_side = "BUY" if direction == "LONG" else "SELL"

    # ── กันเปิดซ้ำ ──
    if get_active(symbol, TIMEFRAME):
        print(f"⚠️ [{symbol}] มี position อยู่แล้ว")
        return False

    # ── คำนวณ quantity จาก estimated entry ──
    balance  = get_balance()
    quantity = calculate_quantity(balance, RISK_PCT, entry_est, sl_orig)
    if quantity <= 0:
        print(f"❌ [{symbol}] quantity = 0 (ยอดไม่พอหรือ SL ชิดเกิน)")
        return False

    # ── เตรียม leverage / margin ──
    set_margin_type(symbol, "ISOLATED")
    set_leverage(symbol, 10)

    # ── เปิดออเดอร์ ──
    order = open_market_order(symbol, open_side, quantity)
    order_id = order.get("orderId")
    if not order_id:
        print(f"❌ [{symbol}] เปิดออเดอร์ไม่สำเร็จ")
        return False

    # ── ดึง fill price จริง ──
    actual_entry = _get_actual_entry(order, entry_est)
    slip_pct = abs(actual_entry - entry_est) / entry_est * 100 if entry_est > 0 else 0
    print(f"✅ [{symbol}] fill = {actual_entry:.6f} | est = {entry_est:.6f} | slip = {slip_pct:.3f}%")

    # ── คำนวณ tp_rr ratio จาก estimated plan ──
    risk_est = abs(entry_est - sl_orig)
    tp_rr = abs(tp2_orig - entry_est) / risk_est if risk_est > 0 else 1.618

    # ── recalculate SL/TP จาก fill price จริง ──
    plan = _recalculate_plan(
        direction=direction,
        actual_entry=actual_entry,
        sl=sl_orig,
        tp_rr=tp_rr,
    )

    # ── validate RR หลัง fill ──
    if not plan["valid"]:
        print(f"❌ [{symbol}] plan ไม่ valid: {plan['reason']} → ปิด position ทันที")
        _emergency_close(symbol, direction, quantity)
        return False

    if plan["rr"] < MIN_RR_AFTER_FILL:
        print(
            f"❌ [{symbol}] RR หลัง fill = {plan['rr']} < {MIN_RR_AFTER_FILL} "
            f"(slip={slip_pct:.3f}%) → ปิด position ทันที"
        )
        _emergency_close(symbol, direction, quantity)
        return False

    sl_final  = plan["sl"]
    tp1_final = plan["tp1"]
    tp2_final = plan["tp2"]
    tp3_final = plan["tp3"]

    print(f"📐 [{symbol}] RR = {plan['rr']} | risk = {plan['risk']} | SL = {sl_final:.6f} | TP3 = {tp3_final:.6f}")

    # ── ตั้ง SL / TP บน exchange ──
    try:
        set_stop_loss(symbol, open_side, quantity, sl_final)
        print(f"✅ [{symbol}] SL = {sl_final}")
    except Exception as e:
        print(f"❌ [{symbol}] ตั้ง SL ล้มเหลว: {e} → ปิด position ทันที")
        _emergency_close(symbol, direction, quantity)
        return False

    try:
        set_take_profit(symbol, open_side, quantity, tp3_final)
        print(f"✅ [{symbol}] TP3 = {tp3_final}")
    except Exception as e:
        print(f"⚠️ [{symbol}] ตั้ง TP ล้มเหลว: {e} (SL ตั้งแล้ว — position ยังอยู่)")

    # ── lock position ด้วย actual plan ──
    lock_new_position(
        symbol=symbol,
        timeframe=TIMEFRAME,
        direction=direction,
        trade_plan={
            "entry": actual_entry,
            "sl":    sl_final,
            "tp1":   tp1_final,
            "tp2":   tp2_final,
            "tp3":   tp3_final,
        },
    )

    print(f"🟢 [{symbol}] execute_signal สำเร็จ | direction={direction} | RR={plan['rr']}")
    return True


def _emergency_close(symbol: str, direction: str, quantity: float) -> None:
    """ปิด position ทันทีด้วย market order ฝั่งตรงข้าม"""
    close_side = "SELL" if direction == "LONG" else "BUY"
    try:
        open_market_order(symbol, close_side, quantity)
        print(f"🔴 [{symbol}] ปิด position (emergency close) สำเร็จ")
    except Exception as e:
        print(f"🚨 [{symbol}] emergency close ล้มเหลว! ต้องปิดมือ: {e}")