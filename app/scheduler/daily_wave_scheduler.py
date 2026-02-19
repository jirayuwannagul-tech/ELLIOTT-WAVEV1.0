import time
import traceback
from datetime import datetime

from app.config.wave_settings import (
    SYMBOLS,
    RUN_HOUR,
    RUN_MINUTE,
    TIMEZONE,
    MAX_RETRY,
)
from app.analysis.wave_engine import analyze_symbol
from app.state.position_manager import get_active, lock_new_position, update_from_price
from app.config.wave_settings import TIMEFRAME
from app.services.telegram_reporter import format_symbol_report, send_message

MIN_CONF_REPORT = 60   # ส่งรายงานเฉพาะเหรียญที่ conf >= 60
MIN_CONF_SIGNAL = 70   # ส่งสัญญาณ/ล็อคโพสิชัน เฉพาะ conf >= 70

def _has_triggered_signal(analysis: dict) -> bool:
    scenarios = analysis.get("scenarios", []) or []

    for sc in scenarios:
        trade = sc.get("trade_plan", {}) or {}
        conf = float(sc.get("confidence") or 0)

        if conf < MIN_CONF_SIGNAL:
            continue

        if not trade.get("valid"):
            continue

        if trade.get("triggered") is not True:
            continue

        entry = float(trade.get("entry") or 0)
        sl = float(trade.get("sl") or 0)
        tp3 = float(trade.get("tp3") or 0)

        risk = abs(entry - sl)
        reward = abs(tp3 - entry)
        if risk <= 0:
            continue

        rr = reward / risk
        if rr < 2.0:
            continue

        return True

    return False

def run_daily_wave_job():
    print(f"=== START DAILY WAVE JOB | tf={TIMEFRAME} | symbols={len(SYMBOLS)} ===", flush=True)

    found = 0
    found_symbols = []
    errors = 0

    for symbol in SYMBOLS:
        print(f"[{symbol}] start", flush=True)
        retry = 0

        while retry < MAX_RETRY:
            try:
                analysis = analyze_symbol(symbol)
                if not analysis:
                    print(f"[{symbol}] no analysis -> skip", flush=True)
                    break

                active = get_active(symbol, TIMEFRAME)
                if active:
                    # ✅ ACTIVE: ส่งอัปเดตทุกวัน (ตามที่คุย)
                    pos, events = update_from_price(symbol, TIMEFRAME, float(analysis["price"]))
                    # ... (บล็อค update ที่คุณทำไว้)
                    break

                scenarios = analysis.get("scenarios", []) or []
                sent = False

                for sc in scenarios:
                    trade = sc.get("trade_plan", {}) or {}
                    conf = float(sc.get("confidence") or 0)
                    if conf < MIN_CONF_SIGNAL:
                        continue

                    if trade.get("valid") and trade.get("triggered") is True:
                        lock_new_position(
                            symbol=symbol,
                            timeframe=TIMEFRAME,
                            direction=sc.get("direction", ""),
                            trade_plan=trade,
                        )
                        text = format_symbol_report(analysis)
                        send_message(text)  # ไปห้องเดียวกันผ่าน TELEGRAM_CHAT_ID
                        print(f"[{symbol}] SENT signal", flush=True)

                        found += 1
                        found_symbols.append(symbol)
                        sent = True
                        break

                if not sent:
                    wl = (analysis.get("wave_label", {}) or {}).get("label", {}) or {}
                    print(f"[{symbol}] no triggered signal | wave={wl.get('pattern')} {wl.get('direction')} conf={wl.get('confidence')}", flush=True)

                break

            except Exception as e:
                retry += 1
                print(f"[{symbol}] ERROR retry={retry}/{MAX_RETRY}: {e}", flush=True)
                if retry >= MAX_RETRY:
                    errors += 1
                    break
                time.sleep(2)

    # ✅ สรุปเช้า: เจอ/ไม่เจอ
    summary = []
    summary.append(f"🕖 DAILY SUMMARY ({TIMEFRAME.upper()})")
    summary.append(f"สแกน: {len(SYMBOLS)} เหรียญ")
    summary.append(f"พบสัญญาณ: {found} เหรียญ")
    summary.append(f"ไม่พบสัญญาณ: {len(SYMBOLS) - found} เหรียญ")
    if found_symbols:
        summary.append("รายการที่พบ: " + ", ".join(found_symbols))
    if errors:
        summary.append(f"⚠️ errors: {errors}")

    send_message("\n".join(summary))

    print("=== END DAILY WAVE JOB ===", flush=True)
    
def start_scheduler_loop():
    """
    Loop เช็คเวลา 20:00 ไทย แล้วรันวันละครั้ง
    """
    print("Wave Scheduler Started...")

    while True:
        now = datetime.now(TIMEZONE)

        if now.hour == RUN_HOUR and now.minute == RUN_MINUTE:
            run_daily_wave_job()
            time.sleep(60)  # กันรันซ้ำในนาทีเดียวกัน

        time.sleep(20)