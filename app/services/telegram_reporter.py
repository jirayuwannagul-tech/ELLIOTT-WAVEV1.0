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
    symbol = analysis.get("symbol", "-")
    price = analysis.get("price")
    macro = analysis.get("macro_trend")
    rsi14 = analysis.get("rsi14")
    vol = analysis.get("volume_spike")
    mtf = analysis.get("mtf") or {}
    mode = analysis.get("mode")
    size_mult = analysis.get("position_size_mult")

    wl = (analysis.get("wave_label") or {}).get("label") or {}
    pivots = wl.get("pivots") or []

    scenarios = analysis.get("scenarios", []) or []
    if not scenarios:
        return f"{symbol} — ไม่มีสัญญาณที่ผ่านเงื่อนไข"

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

    # Pivot list format
    pivot_lines = []
    for i, p in enumerate(pivots, start=1):
        pivot_lines.append(
            f"{i}) {p.get('type')} { _fmt_price(p.get('price')) }"
        )

    pivot_text = "\n".join(pivot_lines) if pivot_lines else "-"

    text = f"""
════════════════════════════
👑 VIP รายงานเชิงลึก — {symbol} (1D)
อัปเดตเวลา 07:05 น.
════════════════════════════

📍 ราคาปัจจุบัน: {_fmt_price(price) if price else '-'}

📊 ภาพรวมตลาด
- แนวโน้มหลัก: {macro}
- สภาพตลาด: {mode}
- RSI14: {round(rsi14,1) if rsi14 else '-'}
- ปริมาณซื้อขายสูงผิดปกติ: {bool(vol)}

📚 มุมมองหลายไทม์เฟรม
- รายสัปดาห์: {mtf.get('weekly_trend')}
- 4 ชั่วโมงยืนยัน: {mtf.get('h4_confirm_long') or mtf.get('h4_confirm_short')}

────────────────────
🧠 โครงสร้าง Elliott Wave
รูปแบบล่าสุด: {wl.get('pattern')}

ลำดับจุดกลับตัว (Pivot)
{pivot_text}

────────────────────
🎯 แผนการเทรด
ทิศทาง: {sc.get('direction')}

เข้าเมื่อราคาปิดเหนือ: {_fmt_price(entry) if entry else '-'}
จุดตัดขาดทุน (SL): {_fmt_price(sl) if sl else '-'}

เป้าหมายกำไร:
TP1: {_fmt_price(tp1) if tp1 else '-'}
TP2: {_fmt_price(tp2) if tp2 else '-'}
TP3: {_fmt_price(tp3) if tp3 else '-'}

ขนาดไม้แนะนำ: {size_mult} เท่า

────────────────────
📌 แนวรับ / แนวต้านใกล้เคียง
แนวรับใกล้สุด: {_fmt_price(support) if support else '-'}
แนวต้านใกล้สุด: {_fmt_price(resist) if resist else '-'}

────────────────────
สถานะสัญญาณ: {"พร้อมเข้า (TRIGGERED)" if trade.get("triggered") else "รอการยืนยัน (WAIT)"}
ระบบจะปิดสถานะเมื่อ:
- ถึง SL หรือ
- ถึง TP3 เท่านั้น
════════════════════════════
""".strip()
    footer = "\n\n────────────────────\n🔵 SYSTEM: ELLIOTT-WAVE\nEngine: 1D\n"
    return text + footer