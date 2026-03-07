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
    TIMEFRAME,
    MIN_CONFIDENCE_LIVE,
)
from app.analysis.wave_engine import analyze_symbol
from app.services.telegram_reporter import format_symbol_report, send_message
from app.state.position_manager import get_active, get_armed_signal, save_armed_signal

def _check_position_from_vps(symbol: str) -> bool:
    """ถาม VPS ว่ามี position เปิดอยู่ไหม"""
    try:
        vps_url = (os.getenv("VPS_URL", "") or "").rstrip("/")
        exec_token = os.getenv("EXEC_TOKEN", "") or ""
        if not vps_url or not exec_token:
            return False

        r = req.get(
            f"{vps_url}/position/status",
            params={"symbol": symbol},
            headers={"X-EXEC-TOKEN": exec_token},
            timeout=5,
        )
        if r.status_code == 200:
            return bool((r.json() or {}).get("active", False))
        return False
    except Exception:
        return False


def _fmt_price(x: float) -> str:
    x = float(x)
    return f"{x:,.5f}" if x < 1 else f"{x:,.2f}"


def _pct_near(a: float, b: float) -> float:
    """abs(a-b)/b *100"""
    if not b:
        return 999.0
    return abs((a - b) / b) * 100.0


def _fallback_scenarios(analysis: dict) -> list:
    """
    fallback เมื่อ wave_engine ไม่คืน scenarios
    - valid: บังคับ True (เพื่อให้มีโอกาสส่งเมื่อ triggered)
    - triggered: ราคาใกล้ entry ภายใน ENTRY_TRIGGER_PCT (%)
    """
    wl = ((analysis.get("wave_label") or {}).get("label") or {}) if analysis else {}
    direction = (wl.get("direction") or "").upper()
    conf = float(wl.get("confidence") or 0)
    price = float(analysis.get("price") or 0)

    pivots = wl.get("pivots") or []
    last_L = None
    last_H = None
    for p in pivots:
        t = (p.get("type") or "").upper()
        if t == "L":
            last_L = p
        elif t == "H":
            last_H = p

    entry = None
    if direction == "LONG" and last_L:
        entry = float(last_L.get("price") or 0)
    elif direction == "SHORT" and last_H:
        entry = float(last_H.get("price") or 0)

    if not entry:
        entry = price

    trigger_pct = float(os.getenv("ENTRY_TRIGGER_PCT", "0.30"))  # default 0.30%
    dist = _pct_near(price, entry)
    triggered = (dist <= trigger_pct) if (price and entry) else False

    # % มาตรฐาน: SL 3%, TP 3/5/7
    sl_pct = float(os.getenv("SL_PCT", "3.0"))
    tp1_pct = float(os.getenv("TP1_PCT", "3.0"))
    tp2_pct = float(os.getenv("TP2_PCT", "5.0"))
    tp3_pct = float(os.getenv("TP3_PCT", "7.0"))

    if direction == "SHORT":
        stop_loss = entry * (1.0 + sl_pct / 100.0)
        tp1 = entry * (1.0 - tp1_pct / 100.0)
        tp2 = entry * (1.0 - tp2_pct / 100.0)
        tp3 = entry * (1.0 - tp3_pct / 100.0)
    else:
        direction = "LONG"
        stop_loss = entry * (1.0 - sl_pct / 100.0)
        tp1 = entry * (1.0 + tp1_pct / 100.0)
        tp2 = entry * (1.0 + tp2_pct / 100.0)
        tp3 = entry * (1.0 + tp3_pct / 100.0)

    sc = {
        "direction": direction,
        "confidence": conf,
        "trade_plan": {
            "valid": True,
            "triggered": bool(triggered),
            "entry": float(entry),
            "sl": float(stop_loss),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "tp3": float(tp3),
            "dist_to_entry_pct": float(dist),
            "source": "fallback_wave_label",
        },
    }
    return [sc]

def run_daily_wave_job():
    print(f"=== START DAILY WAVE JOB | tf={TIMEFRAME} | symbols={len(SYMBOLS)} ===", flush=True)
    print("✅ Binance: SKIP (LOCAL MODE)", flush=True)

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

                db_active = get_active(symbol, TIMEFRAME)
                if db_active:
                    print(f"[{symbol}] DB มี ACTIVE อยู่แล้ว ข้ามไป", flush=True)
                    break

                db_armed = get_armed_signal(symbol, TIMEFRAME)
                if db_armed:
                    print(f"[{symbol}] DB มี ARMED อยู่แล้ว ข้ามไป", flush=True)
                    break

                active = _check_position_from_vps(symbol)
                if active:
                    print(f"[{symbol}] มี position อยู่ที่ VPS แล้ว ข้ามไป", flush=True)
                    break

                scenarios = analysis.get("scenarios", []) or []
                sent = False

                if not scenarios:
                    break

                for sc in scenarios:
                    trade = sc.get("trade_plan", {}) or {}

                    status = (sc.get("status") or "").upper()
                    allowed = bool(trade.get("allowed_to_trade", False))
                    triggered = bool(trade.get("triggered", False))
                    valid = bool(trade.get("valid", False))

                    if status != "READY":
                        continue
                    if not (allowed and triggered and valid):
                        continue

                    direction = (sc.get("direction") or "").upper()
                    entry = float(trade.get("entry") or 0.0)
                    sl = float(trade.get("sl") or 0.0)
                    tp1 = float(trade.get("tp1") or 0.0)
                    tp2 = float(trade.get("tp2") or 0.0)
                    tp3 = float(trade.get("tp3") or 0.0)

                    save_armed_signal(
                        symbol=symbol,
                        timeframe=TIMEFRAME,
                        direction=direction,
                        trigger_price=entry,
                        trade_plan={
                            "entry": entry,
                            "sl": sl,
                            "tp1": tp1,
                            "tp2": tp2,
                            "tp3": tp3,
                        },
                        meta={
                            "confidence": float(sc.get("confidence") or 0.0),
                            "source": "daily_wave_job",
                        },
                    )

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
                        f"[{symbol}] no READY signal | wave={wl.get('pattern')} {wl.get('direction')} conf={wl.get('confidence')}",
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

    summary = []
    summary.append(f"🕖 DAILY SUMMARY ({TIMEFRAME.upper()})")
    summary.append(f"สแกน: {len(SYMBOLS)} เหรียญ")
    summary.append(f"พบสัญญาณ: {found} เหรียญ")
    summary.append(f"ไม่พบสัญญาณ: {len(SYMBOLS) - found} เหรียญ")
    if found_symbols:
        summary.append("รายการที่พบ: " + ", ".join(found_symbols))
    if errors:
        summary.append(f"⚠️ errors: {errors}")

    summary.append("")
    summary.append("────────────────────")
    summary.append("🔵 SYSTEM: ELLIOTT-WAVE")
    summary.append("Engine: 1D")

    send_message("\n".join(summary), topic_id=os.getenv("TOPIC_NORMAL_ID"))
    print("=== END DAILY WAVE JOB ===", flush=True)

def run_trend_watch_job(min_conf: float = 65.0):
    from datetime import datetime
    import pytz

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

                sc = scenarios[0]
                conf = float(sc.get("confidence") or 0)
                if conf < float(min_conf):
                    break

                direction = (sc.get("direction") or "-").upper()
                price = float(analysis.get("price") or 0)

                trade = sc.get("trade_plan", {}) or {}
                entry = trade.get("entry")
                entry = float(entry) if entry is not None else None

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

    picks.sort(key=lambda x: (-x["confidence"], x["dist"] if x["dist"] is not None else 1e9))

    now = datetime.now(pytz.timezone("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append("📡 TREND WATCH (1D)")
    lines.append(f"เกณฑ์: Conf >= {int(min_conf)} | จำนวนที่น่าจับตา: {len(picks)}")
    lines.append("")

    if not picks:
        lines.append("วันนี้ยังไม่มีเหรียญที่เข้าเกณฑ์")
    else:
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

    lines.append("")
    lines.append("────────────────────")
    lines.append(f"📅 {now}")
    lines.append("🔵 SYSTEM: ELLIOTT-WAVE")
    lines.append("Engine: 1D")

    send_message("\n".join(lines), topic_id=os.getenv("TOPIC_NORMAL_ID"))
    print("=== END TREND WATCH ===", flush=True)

def start_scheduler_loop():
    """
    Loop เช็คเวลา RUN_HOUR:RUN_MINUTE ไทย แล้วรันวันละครั้ง
    """
    print("Wave Scheduler Started...", flush=True)

    last_run_date = None  # กันรันซ้ำทั้งวัน

    while True:
        now = datetime.now(TIMEZONE)

        if now.hour == RUN_HOUR and now.minute == RUN_MINUTE:
            today = now.date()
            if last_run_date != today:
                run_daily_wave_job()
                last_run_date = today
            time.sleep(60)  # กันรันซ้ำในนาทีเดียวกัน

        time.sleep(20)