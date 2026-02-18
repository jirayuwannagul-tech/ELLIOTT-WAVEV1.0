def detect_market_mode(df):
    """
    แยกตลาดเป็น TREND หรือ SIDEWAY แบบง่าย
    ใช้ EMA50 / EMA200 + ATR
    """

    if "ema50" not in df.columns or "ema200" not in df.columns:
        return "TREND"

    ema50 = float(df["ema50"].iloc[-1])
    ema200 = float(df["ema200"].iloc[-1])
    atr = float(df["atr14"].iloc[-1]) if "atr14" in df.columns else 0.0
    price = float(df["close"].iloc[-1])

    # ถ้า EMA ใกล้กันมาก + ATR ต่ำ → sideway
    ema_gap_pct = abs(ema50 - ema200) / price * 100

    if ema_gap_pct < 0.5 and atr / price < 0.02:
        return "SIDEWAY"

    return "TREND"