# app/services/telegram_reporter.py
import os
import requests


def _tg_api_url(method: str, token: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_message(text: str, topic_id: str | int | None = None) -> None:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # รองรับหลายชื่อ env
    TELEGRAM_TOPIC_ID = (os.getenv("TELEGRAM_TOPIC_ID") or "").strip()
    TELEGRAM_TOPIC_ID = TELEGRAM_TOPIC_ID.strip()

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n====== TELEGRAM PREVIEW ======")
        print(text)
        print("====== END PREVIEW ======\n")
        return

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    if topic_id is not None and str(topic_id).strip().isdigit():
        payload["message_thread_id"] = int(str(topic_id).strip())
    elif TELEGRAM_TOPIC_ID.isdigit():
        payload["message_thread_id"] = int(TELEGRAM_TOPIC_ID)

    print("TG_SEND chat_id=", TELEGRAM_CHAT_ID,
      "thread=", payload.get("message_thread_id"),
      flush=True)        

    r = requests.post(_tg_api_url("sendMessage", TELEGRAM_BOT_TOKEN), json=payload, timeout=15)
    r.raise_for_status()


def _fmt_price(x: float) -> str:
    x = float(x)
    return f"{x:,.5f}" if x < 1 else f"{x:,.2f}"


def format_symbol_report(analysis: dict) -> str:
    from datetime import datetime
    import pytz

    symbol = analysis.get("symbol", "-")
    size_mult = analysis.get("position_size_mult", 1.0)

    scenarios = analysis.get("scenarios", []) or []
    if not scenarios:
        return f"👑 {symbol} (1D)\nไม่มีสัญญาณ"

    sc = scenarios[0]
    trade = sc.get("trade_plan", {}) or {}

    entry = trade.get("entry")
    sl = trade.get("sl")
    tp1 = trade.get("tp1")
    tp2 = trade.get("tp2")
    tp3 = trade.get("tp3")

    sr = analysis.get("sr") or {}
    support = (sr.get("support") or {}).get("level")
    resist = (sr.get("resist") or {}).get("level")

    direction = sc.get("direction") or "-"

    now = datetime.now(pytz.timezone("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M")

    text = f"""
═══════════════════
👑 {symbol} (1D)

🎯 แผนการเทรด
ทิศทาง: {direction}
Entry: {_fmt_price(entry) if entry else '-'}
SL: {_fmt_price(sl) if sl else '-'}

TP1: {_fmt_price(tp1) if tp1 else '-'}
TP2: {_fmt_price(tp2) if tp2 else '-'}
TP3: {_fmt_price(tp3) if tp3 else '-'}

ขนาดไม้: {size_mult}x
────────────────────
📌 แนวรับ/ต้านใกล้เคียง
แนวรับ: {_fmt_price(support) if support else '-'}
แนวต้าน: {_fmt_price(resist) if resist else '-'}
═══════════════════
📅 {now}
🔵 ELLIOTT-WAVE
Engine: 1D
""".strip()

    return text