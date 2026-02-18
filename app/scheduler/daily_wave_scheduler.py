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

MIN_CONFIDENCE = 60

def _has_triggered_signal(analysis: dict) -> bool:
    scenarios = analysis.get("scenarios", []) or []

    for sc in scenarios:
        trade = sc.get("trade_plan", {}) or {}
        conf = float(sc.get("confidence") or 0)

        # 1) ต้อง confidence ผ่านเกณฑ์
        if conf < MIN_CONFIDENCE:
            continue

        # 2) ต้อง valid + triggered
        if not trade.get("valid"):
            continue

        if trade.get("triggered") is not True:
            continue

        # 3) RR ต้อง >= 2 (กันไม้ขยะ)
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
    """
    วิเคราะห์ครบ 20 เหรียญ แล้วส่ง TG เหรียญละ 1 ข้อความ
    """

    for symbol in SYMBOLS:
        retry = 0

        while retry < MAX_RETRY:
            try:
                analysis = analyze_symbol(symbol)

                if not analysis:
                    break

                # 1) ถ้ามี position ACTIVE -> อัปเดตสถานะ แล้วข้ามการสร้างสัญญาณใหม่
                active = get_active(symbol, TIMEFRAME)
                if active:
                    pos, events = update_from_price(symbol, TIMEFRAME, float(analysis["price"]))

                    # แจ้งเฉพาะ event ใหม่
                    if events.get("tp1") or events.get("tp2") or events.get("tp3") or events.get("sl") or events.get("closed"):
                        lines = []
                        lines.append(f"{symbol} — UPDATE ({TIMEFRAME.upper()})")
                        lines.append(f"ราคา: {analysis['price']}")
                        lines.append(f"สถานะ: {pos.status} | ทิศทาง: {pos.direction}")
                        if events.get("tp1"):
                            lines.append("✅ TP1 HIT")
                        if events.get("tp2"):
                            lines.append("✅ TP2 HIT")
                        if events.get("tp3"):
                            lines.append("✅ TP3 HIT")
                        if events.get("sl"):
                            lines.append("⛔ SL HIT")
                        if events.get("closed"):
                            lines.append(f"🔒 CLOSED: {events.get('closed_reason')}")

                        send_message("\n".join(lines))

                    break

                # 2) ไม่มี ACTIVE -> ส่งเฉพาะ TRIGGERED และ lock ก่อนส่ง
                scenarios = analysis.get("scenarios", []) or []
                for sc in scenarios:
                    trade = sc.get("trade_plan", {}) or {}
                    if trade.get("valid") and trade.get("triggered") is True:
                        # lock กันทับ/ซ้อน
                        lock_new_position(
                            symbol=symbol,
                            timeframe=TIMEFRAME,
                            direction=sc.get("direction", ""),
                            trade_plan=trade,
                        )
                        text = format_symbol_report(analysis)
                        send_message(text)
                        break

                break

            except Exception as e:
                retry += 1
                if retry >= MAX_RETRY:
                    error_text = (
                        f"{symbol} — ERROR หลัง retry {MAX_RETRY} ครั้ง\n"
                        f"{str(e)}"
                    )
                    try:
                        send_message(error_text)
                    except:
                        pass

                time.sleep(2)

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