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
                    pos, events = update_from_price(
                        symbol,
                        TIMEFRAME,
                        float(analysis["price"])
                    )
                    break

                scenarios = analysis.get("scenarios", []) or []
                sent = False

                for sc in scenarios:
                    trade = sc.get("trade_plan", {}) or {}

                    if not trade.get("valid"):
                        continue

                    if trade.get("triggered") is not True:
                        continue

                    ok = lock_new_position(
                        symbol=symbol,
                        timeframe=TIMEFRAME,
                        direction=sc.get("direction", ""),
                        trade_plan=trade,
                    )

                    if not ok:
                        continue

                    text = format_symbol_report(analysis)
                    send_message(text)

                    print(f"[{symbol}] SENT signal", flush=True)

                    found += 1
                    found_symbols.append(symbol)
                    sent = True
                    break

                if not sent:
                    wl = (analysis.get("wave_label", {}) or {}).get("label", {}) or {}
                    print(
                        f"[{symbol}] no triggered signal | "
                        f"wave={wl.get('pattern')} "
                        f"{wl.get('direction')} "
                        f"conf={wl.get('confidence')}",
                        flush=True
                    )

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