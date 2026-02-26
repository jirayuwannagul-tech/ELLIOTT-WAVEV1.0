# app/trading/position_watcher.py
import os
import time
import threading

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

def _loop():
    while True:
        try:
            actives = list_active_positions(TIMEFRAME)
            for pos in actives:
                sym = pos.symbol

                live = _find_live_position(sym)
                if not live:
                    # ถ้าใน Binance ไม่มีแล้ว → ปิดใน DB
                    pos.status = "CLOSED"
                    pos.closed_reason = pos.closed_reason or "EXTERNAL_CLOSE"
                    pos.closed_at = pos.closed_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    _save_position(_key(sym, pos.timeframe), asdict(pos))
                    continue

                amt = float(live.get("positionAmt") or 0)
                cur_qty = abs(amt)
                if cur_qty <= 0:
                    continue

                direction = (pos.direction or "").upper()
                mark = float(live.get("markPrice") or 0) or get_mark_price(sym)

                # ฝั่งปิด + positionSide
                if amt > 0:
                    close_side = "SELL"
                    pos_side = "LONG"
                else:
                    close_side = "BUY"
                    pos_side = "SHORT"

                if not IS_HEDGE_MODE:
                    pos_side = None

                # SL ก่อน
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

                # TP1
                tp1_hit = (mark >= pos.tp1) if direction == "LONG" else (mark <= pos.tp1)
                if (not pos.tp1_hit) and tp1_hit:
                    q = min(cur_qty, pos.qty * W1)
                    if _close_qty(sym, close_side, q, pos_side):
                        pos.tp1_hit = True
                        pos.remaining_qty = max(0.0, pos.remaining_qty - q)
                        _save_position(_key(sym, pos.timeframe), asdict(pos))

                # TP2
                tp2_hit = (mark >= pos.tp2) if direction == "LONG" else (mark <= pos.tp2)
                if (not pos.tp2_hit) and tp2_hit:
                    q = min(cur_qty, pos.qty * W2)
                    if _close_qty(sym, close_side, q, pos_side):
                        pos.tp2_hit = True
                        pos.remaining_qty = max(0.0, pos.remaining_qty - q)
                        _save_position(_key(sym, pos.timeframe), asdict(pos))

                # TP3 (ปิดที่เหลือทั้งหมด)
                tp3_hit = (mark >= pos.tp3) if direction == "LONG" else (mark <= pos.tp3)
                if (not pos.tp3_hit) and tp3_hit:
                    if _close_qty(sym, close_side, cur_qty, pos_side):
                        pos.tp3_hit = True
                        pos.status = "CLOSED"
                        pos.closed_reason = "TP3"
                        pos.closed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        pos.remaining_qty = 0.0
                        _save_position(_key(sym, pos.timeframe), asdict(pos))

        except Exception:
            pass

        time.sleep(WATCH_SEC)

def start_position_watcher():
    global _T
    if _T and _T.is_alive():
        return
    _T = threading.Thread(target=_loop, daemon=True)
    _T.start()