# app/trading/position_watcher.py
import os
import time
import threading

from app.state.position_manager import list_armed_signals, clear_armed_signal
from app.trading.trade_executor import execute_signal
from app.config.wave_settings import TIMEFRAME
from app.state.position_manager import list_active_positions, _key, _save_position, asdict  # type: ignore
from app.trading.binance_trader import (
    get_open_positions,
    get_mark_price,
    close_market_reduce_only,
    adjust_quantity,
    IS_HEDGE_MODE,
)

_T = None

W1 = float(os.getenv("TP1_WEIGHT", "0.30"))
W2 = float(os.getenv("TP2_WEIGHT", "0.30"))
W3 = float(os.getenv("TP3_WEIGHT", "0.40"))
WATCH_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "5"))

def _find_live_position(symbol: str):
    for p in get_open_positions():
        if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0:
            return p
    return None

def _close_qty(symbol: str, close_side: str, qty: float, pos_side: str | None):
    qty = adjust_quantity(symbol, qty)
    if qty <= 0:
        return False
    close_market_reduce_only(symbol, close_side, qty, position_side=pos_side)
    return True

def _armed_triggered(direction: str, mark: float, trigger: float) -> bool:
    d = (direction or "").upper()
    if d == "LONG":
        return mark >= trigger
    if d == "SHORT":
        return mark <= trigger
    return False

def _loop():
    while True:
        try:
            # =========================
            # ARMED SIGNALS (pending trigger)
            # =========================
            armed = list_armed_signals(TIMEFRAME)
            for s in armed:
                sym = (s.get("symbol") or "").upper()
                direction = (s.get("direction") or "").upper()
                trigger_price = float(s.get("trigger_price") or 0.0)

                if not sym or trigger_price <= 0:
                    continue

                # ถ้ามี position อยู่แล้ว → เคลียร์ ARMED กันซ้ำ
                live = _find_live_position(sym)
                if live:
                    clear_armed_signal(sym, TIMEFRAME)
                    continue

                try:
                    mark = get_mark_price(sym)
                except Exception:
                    mark = 0.0

                if mark <= 0:
                    continue

                if _armed_triggered(direction, mark, trigger_price):
                    payload = {
                        "symbol": sym,
                        "direction": direction,
                        "trade_plan": s.get("trade_plan") or {},
                        "meta": s.get("meta") or {},
                    }
                    execute_signal(payload)
                    # เคลียร์เพื่อไม่ยิงซ้ำทุก 5 วิ
                    clear_armed_signal(sym, TIMEFRAME)

            actives = list_active_positions(TIMEFRAME)
            for pos in actives:
                sym = pos.symbol

                live = _find_live_position(sym)
                if not live:
                    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                    # ดึง mark price ล่าสุดเพื่อเทียบ
                    try:
                        mark = get_mark_price(sym)
                    except Exception:
                        mark = 0.0

                    # เทียบราคากับ SL/TP ใน DB
                    direction = (pos.direction or "").upper()
                    if mark > 0:
                        if direction == "LONG":
                            if mark <= pos.sl:
                                pos.sl_hit = True
                                pos.closed_reason = "SL"
                            elif mark >= pos.tp3:
                                pos.tp3_hit = True
                                pos.closed_reason = "TP3"
                            else:
                                pos.closed_reason = "EXTERNAL_CLOSE"
                        else:  # SHORT
                            if mark >= pos.sl:
                                pos.sl_hit = True
                                pos.closed_reason = "SL"
                            elif mark <= pos.tp3:
                                pos.tp3_hit = True
                                pos.closed_reason = "TP3"
                            else:
                                pos.closed_reason = "EXTERNAL_CLOSE"
                    else:
                        pos.closed_reason = pos.closed_reason or "EXTERNAL_CLOSE"

                    pos.status = "CLOSED"
                    pos.closed_at = pos.closed_at or now_str
                    _save_position(_key(sym, pos.timeframe), asdict(pos))
                    continue

                amt = float(live.get("positionAmt") or 0)
                cur_qty = abs(amt)
                if cur_qty <= 0:
                    continue

                direction = (pos.direction or "").upper()
                mark = float(live.get("markPrice") or 0) or get_mark_price(sym)

                if amt > 0:
                    close_side = "SELL"
                    pos_side = "LONG"
                else:
                    close_side = "BUY"
                    pos_side = "SHORT"

                if not IS_HEDGE_MODE:
                    pos_side = None

                sl_hit = (mark <= pos.sl) if direction == "LONG" else (mark >= pos.sl)
                if (not pos.sl_hit) and sl_hit:
                    if _close_qty(sym, close_side, cur_qty, pos_side):
                        pos.sl_hit = True
                        pos.status = "CLOSED"
                        pos.closed_reason = "SL"
                        pos.closed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        pos.remaining_qty = 0.0
                        _save_position(_key(sym, pos.timeframe), asdict(pos))
                    continue

                tp1_hit = (mark >= pos.tp1) if direction == "LONG" else (mark <= pos.tp1)
                if (not pos.tp1_hit) and tp1_hit:
                    q = min(cur_qty, pos.qty * W1)
                    if _close_qty(sym, close_side, q, pos_side):
                        pos.tp1_hit = True
                        pos.remaining_qty = max(0.0, pos.remaining_qty - q)
                        _save_position(_key(sym, pos.timeframe), asdict(pos))

                tp2_hit = (mark >= pos.tp2) if direction == "LONG" else (mark <= pos.tp2)
                if (not pos.tp2_hit) and tp2_hit:
                    q = min(cur_qty, pos.qty * W2)
                    if _close_qty(sym, close_side, q, pos_side):
                        pos.tp2_hit = True
                        pos.remaining_qty = max(0.0, pos.remaining_qty - q)
                        _save_position(_key(sym, pos.timeframe), asdict(pos))

                tp3_hit = (mark >= pos.tp3) if direction == "LONG" else (mark <= pos.tp3)
                if (not pos.tp3_hit) and tp3_hit:
                    if _close_qty(sym, close_side, cur_qty, pos_side):
                        pos.tp3_hit = True
                        pos.status = "CLOSED"
                        pos.closed_reason = "TP3"
                        pos.closed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        pos.remaining_qty = 0.0
                        _save_position(_key(sym, pos.timeframe), asdict(pos))

        except Exception as e:
            import traceback
            print("WATCHER_ERROR:", e, flush=True)
            print(traceback.format_exc(), flush=True)

        time.sleep(WATCH_SEC)

def start_position_watcher():
    global _T
    if _T and _T.is_alive():
        return
    _T = threading.Thread(target=_loop, daemon=True)
    _T.start()