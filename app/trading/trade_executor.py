# app/trading/trade_executor.py

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

import os
DRY_RUN = os.getenv("DRY_RUN", "0").lower() in ("1", "true", "yes")

from app.trading.binance_trader import (
    get_balance,
    open_market_order,
    set_stop_loss,
    set_take_profit,
    set_leverage,
    set_margin_type,
    adjust_quantity,
)

from app.trading.position_sizer import calculate_quantity
from app.state.position_manager import lock_new_position, get_active
from app.config.wave_settings import TIMEFRAME

RISK_PCT = 0.02
MIN_NOTIONAL_USDT = 20.0

FIXED_NOTIONAL_USDT = {
    "BTCUSDT": 70.0,
}

def _get_actual_entry(order: dict, entry_est: float) -> float:
    avg = float(order.get("avgPrice") or 0)
    if avg > 0:
        return avg
    fills = order.get("fills") or []
    if fills:
        total_qty = sum(float(f["qty"]) for f in fills)
        if total_qty > 0:
            return sum(float(f["price"]) * float(f["qty"]) for f in fills) / total_qty
    return entry_est


def _recalculate_plan(direction: str, actual_entry: float, sl: float, tp_rr: float) -> dict:
    direction = direction.upper()
    risk = abs(actual_entry - sl)
    if risk <= 0:
        return {"valid": False, "reason": "risk=0 (entry==sl)"}
    if direction == "LONG":
        tp1 = actual_entry + risk * 1.0
        tp2 = actual_entry + risk * tp_rr
        tp3 = actual_entry + risk * (tp_rr + 0.382)
    else:
        tp1 = actual_entry - risk * 1.0
        tp2 = actual_entry - risk * tp_rr
        tp3 = actual_entry - risk * (tp_rr + 0.382)
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

    # ✅ DRY RUN
    if DRY_RUN:
        balance = float(signal.get("balance") or os.getenv("DRY_BALANCE", "178"))
        quantity = calculate_quantity(balance, RISK_PCT, entry_est, sl_orig)
        if quantity <= 0:
            print(f"❌ [{symbol}] quantity = 0")
            return False
        print("🧪 DRY_RUN=1 → ไม่ยิงออเดอร์จริง")
        print(f"[{symbol}] side={open_side} balance={balance} qty={quantity} entry_est={entry_est} sl={sl_orig} tp2={tp2_orig}")
        return True

    # ── ของจริง ──
    balance = get_balance()

    fixed_notional = FIXED_NOTIONAL_USDT.get(symbol)
    if fixed_notional is not None:
        quantity = fixed_notional / entry_est if entry_est > 0 else 0.0
    else:
        quantity = calculate_quantity(balance, RISK_PCT, entry_est, sl_orig)

    if quantity <= 0:
        print(f"❌ [{symbol}] quantity = 0")
        return False

    # ── CAP SIZE BY MARGIN ──
    LEVERAGE = 10
    MAX_MARGIN_PCT = 0.10
    max_notional = balance * MAX_MARGIN_PCT * LEVERAGE
    notional = quantity * entry_est
    if notional > max_notional and entry_est > 0:
        quantity = round(max_notional / entry_est, 6)

    # ── เตรียม leverage / margin ──
    set_margin_type(symbol, "ISOLATED")
    set_leverage(symbol, LEVERAGE)

    # ── กัน quantity เล็กจนปรับแล้วเป็น 0 ──
    adj_qty = adjust_quantity(symbol, quantity)
    if adj_qty <= 0:
        print(f"❌ [{symbol}] skip: qty too small after adjust (raw={quantity})", flush=True)
        return False
    quantity = adj_qty

    # ── pre-check minimum notional $20 (Binance requirement) ──
    _notional_est = quantity * entry_est
    if _notional_est < MIN_NOTIONAL_USDT:
        print(f"❌ [{symbol}] notional ต่ำเกิน ${_notional_est:.2f} < ${MIN_NOTIONAL_USDT} → skip", flush=True)
        return False

    # ── เปิดออเดอร์ ──
    order = open_market_order(symbol, open_side, quantity)
    order_id = order.get("orderId")
    if not order_id:
        print(f"❌ [{symbol}] เปิดออเดอร์ไม่สำเร็จ")
        return False

    # ── ดึง fill price จริง ──
    actual_entry = _get_actual_entry(order, entry_est)
    slip_pct = abs(actual_entry - entry_est) / entry_est * 100 if entry_est > 0 else 0
    print(f"✅ [{symbol}] fill = {actual_entry:.6f} | slip = {slip_pct:.3f}%")

    risk_est = abs(entry_est - sl_orig)
    tp_rr = abs(tp2_orig - entry_est) / risk_est if risk_est > 0 else 1.618

    plan = _recalculate_plan(
        direction=direction,
        actual_entry=actual_entry,
        sl=sl_orig,
        tp_rr=tp_rr,
    )

    if not plan["valid"]:
        print(f"❌ [{symbol}] plan invalid → emergency close")
        _emergency_close(symbol, direction, quantity)
        return False

    sl_final = plan["sl"]

    if direction.upper() == "LONG":
        tp_final = max(float(plan["tp2"]), float(plan["tp3"]))
    else:
        tp_final = min(float(plan["tp2"]), float(plan["tp3"]))

    print(f"📐 RR={plan['rr']} | SL={sl_final:.6f} | TP={tp_final:.6f}")

    try:
        set_stop_loss(symbol, open_side, quantity, sl_final)
        print("✅ SL set")
    except Exception:
        print("❌ SL fail → emergency close")
        _emergency_close(symbol, direction, quantity)
        return False

    try:
        set_take_profit(symbol, open_side, quantity, tp_final)
        print("✅ TP set")
    except Exception:
        print("❌ TP fail → emergency close")
        _emergency_close(symbol, direction, quantity)
        return False

    lock_new_position(
        symbol=symbol,
        timeframe=TIMEFRAME,
        direction=direction,
        trade_plan={
            "entry": actual_entry,
            "sl":    sl_final,
            "tp1":   float(plan["tp1"]),
            "tp2":   float(plan["tp2"]),
            "tp3":   float(tp_final),
            "qty":   float(quantity),
            "rr":    float(plan["rr"]),
            "risk":  float(plan["risk"]),
            "balance_at_open": float(balance),
        },
    )

    print(f"🟢 execute_signal สำเร็จ")
    return True


def _emergency_close(symbol: str, direction: str, quantity: float) -> None:
    close_side = "SELL" if direction == "LONG" else "BUY"
    try:
        open_market_order(symbol, close_side, quantity)
        print(f"🔴 [{symbol}] ปิด position (emergency close) สำเร็จ")
    except Exception as e:
        print(f"🚨 [{symbol}] emergency close ล้มเหลว! ต้องปิดมือ: {e}")