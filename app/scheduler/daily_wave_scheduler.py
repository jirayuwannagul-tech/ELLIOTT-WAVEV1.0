import time
import os
import requests as req
from datetime import datetime

from app.config.wave_settings import (
    SYMBOLS,
    RUN_HOUR,
    RUN_MINUTE,
    TIMEZONE,
    MAX_RETRY,
)
from app.analysis.wave_engine import analyze_symbol
from app.config.wave_settings import TIMEFRAME
from app.services.telegram_reporter import format_symbol_report, send_message
from app.trading.binance_trader import get_balance

def _check_position_from_vps(symbol: str) -> bool:
    """ถาม VPS ว่ามี position เปิดอยู่ไหม"""
    try:
        vps_url = os.getenv("VPS_URL", "")
        exec_token = os.getenv("EXEC_TOKEN", "")
        r = req.get(
            f"{vps_url}/position/status",
            params={"symbol": symbol},
            headers={"X-EXEC-TOKEN": exec_token},
            timeout=5,
        )
        if r.status_code == 200:
            return bool(r.json().get("active", False))
        return False
    except Exception:
        return False
    
def _fmt_price(x: float) -> str:
    x = float(x)
    return f"{x:,.5f}" if x < 1 else f"{x:,.2f}"

def run_daily_wave_job():
    print(f"=== START DAILY WAVE JOB | tf={TIMEFRAME} | symbols={len(SYMBOLS)} ===", flush=True)

    try:
        balance = get_balance()
        print(f"✅ Binance พร้อม | ยอด USDT = {balance:.2f}", flush=True)
    except Exception as e:
        print(f"❌ Binance เชื่อมต่อไม่ได้: {e}", flush=True)

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

                active = _check_position_from_vps(symbol)
                if active:
                    print(f"[{symbol}] มี position อยู่ที่ VPS แล้ว ข้ามไป", flush=True)
                    break

                scenarios = analysis.get("scenarios", []) or []
                sent = False

                for sc in scenarios:
                    trade = sc.get("trade_plan", {}) or {}

                    if not trade.get("valid"):
                        continue

                    if trade.get("triggered") is not True:
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

    try:
        balance = get_balance()
        summary.append(f"💰 ยอด USDT: {balance:.2f}")
    except Exception:
        pass

    # ✅ เพิ่มตรงนี้
    summary.append("")
    summary.append("────────────────────")
    summary.append("🔵 SYSTEM: ELLIOTT-WAVE")
    summary.append("Engine: 1D")

    send_message("\n".join(summary), topic_id=os.getenv("TOPIC_NORMAL_ID"))

    print("=== END DAILY WAVE JOB ===", flush=True)
    
def run_trend_watch_job(min_conf: float = 65.0):
    """
    Trend Watch (19:00): ใช้ 1D scenarios (ไม่ต้อง triggered)
    - ไม่ lock position
    - ไม่ update position
    - แจ้งเฉพาะเหรียญที่ confidence >= min_conf
    """
    print(f"=== START TREND WATCH | tf={TIMEFRAME} | min_conf={min_conf} ===", flush=True)

    picks = []
    errors = 0

    for symbol in SYMBOLS:
        retry = 0
        while retry < MAX_RETRY:
            try:
                analysis = analyze_symbol(symbol)
                if not analysis:
                    break

                scenarios = analysis.get("scenarios", []) or []
                if not scenarios:
                    break

                # ใช้ scenario อันดับ 1 (คะแนนสูงสุดใน wave_engine)
                sc = scenarios[0]
                conf = float(sc.get("confidence") or 0)
                if conf < float(min_conf):
                    break

                direction = (sc.get("direction") or "-").upper()
                price = float(analysis.get("price") or 0)

                trade = sc.get("trade_plan", {}) or {}
                entry = trade.get("entry")
                entry = float(entry) if entry is not None else None

                # ระยะห่างถึง entry (%)
                dist = None
                if entry and price:
                    dist = abs((entry - price) / price) * 100.0

                picks.append({
                    "symbol": symbol,
                    "direction": direction,
                    "confidence": conf,
                    "price": price,
                    "entry": entry,
                    "dist": dist,
                })
                break

            except Exception as e:
                retry += 1
                print(f"[{symbol}] TREND WATCH ERROR retry={retry}/{MAX_RETRY}: {e}", flush=True)
                if retry >= MAX_RETRY:
                    errors += 1
                    break
                time.sleep(1)

    # เรียง: conf มากก่อน แล้ว dist ใกล้ก่อน
    picks.sort(key=lambda x: (-x["confidence"], x["dist"] if x["dist"] is not None else 1e9))

    lines = []
    lines.append("📡 TREND WATCH (1D) — 19:00")
    lines.append(f"เกณฑ์: Conf >= {int(min_conf)} | จำนวนที่น่าจับตา: {len(picks)}")
    lines.append("")

    if not picks:
        lines.append("วันนี้ยังไม่มีเหรียญที่เข้าเกณฑ์ (รอดูแท่งปิด 1D ตามรอบปกติ)")
    else:
        # กันยาวเกิน: ส่งแค่ TOP 10
        top = picks[:10]
        for i, p in enumerate(top, start=1):
            sym = p["symbol"]
            d = p["direction"]
            conf = round(p["confidence"], 1)
            price = p["price"]
            entry = p["entry"]
            dist = p["dist"]

            if entry is not None and dist is not None:
                lines.append(f"{i}) {sym} {d} | Conf {conf} | ราคา {_fmt_price(price)} | Entry {_fmt_price(entry)} | ห่าง {dist:.2f}%")
            else:
                lines.append(f"{i}) {sym} {d} | Conf {conf} | ราคา {_fmt_price(price)}")

        if len(picks) > 10:
            lines.append("")
            lines.append(f"…และมีอีก {len(picks) - 10} เหรียญที่เข้าเกณฑ์")

    if errors:
        lines.append("")
        lines.append(f"⚠️ errors: {errors}")

    # ✅ เพิ่มตรงนี้
    lines.append("")
    lines.append("────────────────────")
    lines.append("🔵 SYSTEM: ELLIOTT-WAVE")
    lines.append("Engine: 1D")

    send_message("\n".join(lines), topic_id=os.getenv("TOPIC_NORMAL_ID"))
    print("=== END TREND WATCH ===", flush=True)

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