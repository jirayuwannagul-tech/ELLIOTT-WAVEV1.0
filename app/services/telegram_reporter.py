# app/services/telegram_reporter.py
import os
import requests


def _tg_api_url(method: str, token: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_message(text: str) -> None:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    TELEGRAM_TOPIC_ID = os.getenv("TELEGRAM_TOPIC_ID", "").strip()

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

    if TELEGRAM_TOPIC_ID.isdigit():
        payload["message_thread_id"] = int(TELEGRAM_TOPIC_ID)

    r = requests.post(_tg_api_url("sendMessage", TELEGRAM_BOT_TOKEN), json=payload, timeout=15)
    r.raise_for_status()


def _fmt_price(x: float) -> str:
    x = float(x)
    return f"{x:,.5f}" if x < 1 else f"{x:,.2f}"


def format_symbol_report(analysis: dict) -> str:
    symbol = analysis.get("symbol", "-")
    price = analysis.get("price", None)
    y = analysis.get("close_yesterday")
    t = analysis.get("close_today")

    scenarios = analysis.get("scenarios", []) or []
    macro = analysis.get("macro_trend")
    rsi14 = analysis.get("rsi14")
    vol = analysis.get("volume_spike")
    mtf = analysis.get("mtf") or {}

    lines = []
    lines.append(f"{symbol} — 1D (อัปเดต 07:05)")
    if price is not None:
        lines.append(f"ราคาอ้างอิง: {_fmt_price(price)}")
    if y is not None and t is not None:
        lines.append(f"เมื่อวาน: {_fmt_price(y)} | วันนี้: {_fmt_price(t)}")
    lines.append("")

    if not scenarios:
        msg = analysis.get("message") or "ยังไม่มี scenario ที่ผ่านกฎ"
        lines.append(f"สรุป: {msg}")
        lines.append(f"- Macro: {macro} | RSI14: {rsi14:.1f} | VolSpike: {bool(vol)}")
        if mtf:
            lines.append(
                f"- MTF: W={mtf.get('weekly_trend')} permit(L/S)={mtf.get('weekly_permit_long')}/{mtf.get('weekly_permit_short')} "
                f"| H4={mtf.get('h4_trend')} confirm(L/S)={mtf.get('h4_confirm_long')}/{mtf.get('h4_confirm_short')}"
            )
        wl = (analysis.get("wave_label") or {}).get("label")
        if wl:
            lines.append(f"- Wave ล่าสุด: {wl.get('pattern')} {wl.get('direction')} | conf={wl.get('confidence')}")
        return "\n".join(lines)

    lines.append("สัญญาณที่ผ่านกฎ (เฉพาะ Trigger/Ready):")
    for i, sc in enumerate(scenarios, start=1):
        direction = sc.get("direction", "-")
        conf = sc.get("confidence")
        cs = sc.get("context_score")
        trade = sc.get("trade_plan", {}) or {}
        entry = trade.get("entry")
        sl = trade.get("sl")
        tp1 = trade.get("tp1")
        tp2 = trade.get("tp2")
        tp3 = trade.get("tp3")

        lines.append(f"{i}) {direction} | Conf:{conf} | Context:{cs}")
        if entry is not None:
            lines.append(f"   เข้าเมื่อปิดผ่าน Entry: {_fmt_price(entry)}")
        if sl is not None:
            lines.append(f"   SL: {_fmt_price(sl)}")
        if tp1 is not None and tp2 is not None and tp3 is not None:
            lines.append(f"   TP: {_fmt_price(tp1)} / {_fmt_price(tp2)} / {_fmt_price(tp3)}")
        lines.append(f"   Status: {'TRIGGERED' if trade.get('triggered') else 'WAIT'} | {trade.get('reason','')}")
        lines.append("")

    return "\n".join(lines).strip()