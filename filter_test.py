"""
filter_test.py
รันเพื่อทดสอบผลกระทบของตัวกรองแต่ละตัว
วิธีรัน: python filter_test.py
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from typing import Dict, List, Optional

import pandas as pd

logging.basicConfig(level=logging.WARNING)

# ---- import จากระบบจริง ----
from app.data.binance_fetcher import fetch_ohlcv, drop_unclosed_candle
from app.analysis.pivot import find_fractal_pivots, filter_pivots
from app.analysis.wave_scenarios import build_scenarios
from app.risk.risk_manager import build_trade_plan
from app.indicators.ema import add_ema
from app.indicators.rsi import add_rsi
from app.indicators.atr import add_atr
from app.indicators.volume import add_volume_ma, volume_spike
from app.indicators.trend_filter import trend_filter_ema, allow_direction
from app.analysis.context_gate import apply_context_gate
from app.analysis.market_regime import detect_market_regime
from app.analysis.macro_bias import compute_macro_bias
from app.config.wave_settings import ABC_CONFIRM_BUFFER

_START_BAR = 250

# ================================================================
# FLAGS — ปิด/เปิดตัวกรองแต่ละตัวตรงนี้
# True = เปิดใช้งาน (default), False = ปิดทดสอบ
# ================================================================
FLAGS = {
    "F_ATR_COMPRESSION":  True,   # B02: atr >= atr_ma50
    "F_TREND_DIRECTION":  True,   # B04: allow_direction
    "F_RSI_MIDLINE":      True,   # B05/B06: rsi14 vs 50
    "F_MIN_CONFIDENCE":   True,   # C01: conf < min_confidence
    "F_MACRO_BIAS":       True,   # C02/C03: allow_long/short
    "F_RR_VALID":         True,   # B07: trade_plan.valid
    "F_TRIGGER_PRICE":    True,   # B08: triggered
}

MIN_CONFIDENCE_BACKTEST = 55


def _prepare_df(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    df = fetch_ohlcv(symbol, interval=interval, limit=limit)
    df = drop_unclosed_candle(df)
    if df is None or len(df) < _START_BAR:
        return None
    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)
    return df


def _simulate_one_trade(df, start_i, direction, entry, sl, tp3) -> Dict:
    for i in range(start_i, len(df)):
        high = float(df["high"].iloc[i])
        low  = float(df["low"].iloc[i])
        if direction == "LONG":
            if low  <= sl:  return {"result": "LOSS", "bars": i - start_i}
            if high >= tp3: return {"result": "WIN",  "bars": i - start_i}
        else:
            if high >= sl:  return {"result": "LOSS", "bars": i - start_i}
            if low  <= tp3: return {"result": "WIN",  "bars": i - start_i}
    return {"result": "OPEN", "bars": len(df) - start_i}


def run_backtest_with_flags(symbol: str, interval="1d", limit=1000, min_rr=2.0) -> Dict:
    """รัน backtest ด้วย FLAGS ปัจจุบัน"""
    invalid_reasons = Counter()
    df = _prepare_df(symbol, interval, limit)
    if df is None:
        return {"symbol": symbol, "trades": 0, "skipped": {}}

    trades: List[Dict] = []
    skipped = Counter()
    in_position = False
    skip_until_bar = 0

    for i in range(_START_BAR, len(df) - 1):
        if in_position or i < skip_until_bar:
            continue

        sub        = df.iloc[:i + 1].copy()
        macro_trend = trend_filter_ema(sub)
        rsi14      = float(sub["rsi14"].iloc[-1])
        is_vol     = bool(volume_spike(sub, length=20, multiplier=1.5))
        last_close = float(sub["close"].iloc[-1])

        # --- F_ATR_COMPRESSION ---
        if FLAGS["F_ATR_COMPRESSION"]:
            atr     = float(sub["atr14"].iloc[-1])
            atr_ma  = float(sub["atr14"].rolling(50).mean().iloc[-1]) if len(sub) >= 50 else 0.0
            if atr_ma > 0 and atr >= atr_ma:
                skipped["ATR_COMPRESSION"] += 1
                continue

        # --- build scenarios ---
        pivots = find_fractal_pivots(sub)
        pivots = filter_pivots(pivots, min_pct_move=1.5)
        if len(pivots) < 4:
            skipped["PIVOT_COUNT"] += 1
            continue

        scenarios = build_scenarios(pivots, macro_trend=macro_trend,
                                    rsi14=rsi14, volume_spike=is_vol)
        if not scenarios:
            skipped["NO_SCENARIO"] += 1
            continue

        # --- F_MIN_CONFIDENCE / F_MACRO_BIAS via context_gate ---
        regime     = detect_market_regime(sub)
        macro_bias = compute_macro_bias(regime, rsi14=rsi14)

        # ถ้าปิด F_MACRO_BIAS → บังคับ allow ทั้งคู่
        if not FLAGS["F_MACRO_BIAS"]:
            macro_bias["allow_long"]  = True
            macro_bias["allow_short"] = True

        conf_threshold = MIN_CONFIDENCE_BACKTEST if FLAGS["F_MIN_CONFIDENCE"] else 0.0

        gated = []
        for sc in scenarios:
            r = apply_context_gate(sc, macro_bias=macro_bias, min_confidence=conf_threshold)
            if r:
                gated.append(r)
            else:
                skipped["CONTEXT_GATE"] += 1

        if not gated:
            continue

        sc        = gated[0]
        direction = sc["direction"]

        # --- F_TREND_DIRECTION ---
        if FLAGS["F_TREND_DIRECTION"]:
            if not allow_direction(macro_trend, direction):
                skipped["TREND_DIRECTION"] += 1
                continue

        # --- F_RSI_MIDLINE ---
        if FLAGS["F_RSI_MIDLINE"]:
            if direction == "LONG"  and rsi14 < 50:
                skipped["RSI_MIDLINE"] += 1
                continue
            if direction == "SHORT" and rsi14 > 50:
                skipped["RSI_MIDLINE"] += 1
                continue

        trade_plan = build_trade_plan(sc, current_price=last_close, min_rr=min_rr)

        # --- F_RR_VALID ---
        if FLAGS["F_RR_VALID"]:
            if not trade_plan.get("valid"):
                skipped["RR_INVALID"] += 1
                invalid_reasons[str(trade_plan.get("reason") or "NO_REASON")] += 1
                continue
        else:
            # ถ้าปิด F_RR_VALID แต่ไม่มี entry ก็ข้ามไป
            if trade_plan.get("entry") is None:
                skipped["NO_ENTRY"] += 1
                continue

        entry = float(trade_plan["entry"])
        sl    = float(trade_plan.get("sl") or entry * 0.97)
        tp3   = float(trade_plan.get("tp3") or entry * 1.07)

        # --- F_TRIGGER_PRICE ---
        stype = (sc.get("type") or "").upper()
        if stype == "ABC_UP":
            triggered = last_close > float(trade_plan.get("sl", 0)) * (1 + ABC_CONFIRM_BUFFER)
        elif stype == "ABC_DOWN":
            triggered = last_close < float(trade_plan.get("sl", 0)) * (1 - ABC_CONFIRM_BUFFER)
        else:
            triggered = (
                (direction == "LONG"  and last_close > entry) or
                (direction == "SHORT" and last_close < entry)
            )

        if FLAGS["F_TRIGGER_PRICE"] and not triggered:
            skipped["TRIGGER_PRICE"] += 1
            continue

        in_position = True
        sim = _simulate_one_trade(df, i + 1, direction, entry, sl, tp3)

        trades.append({
            "symbol":     symbol,
            "bar_index":  i,
            "direction":  direction,
            "confidence": float(sc.get("confidence") or 0),
            "entry":      entry,
            "sl":         sl,
            "tp3":        tp3,
            "result":     sim["result"],
            "bars_held":  sim["bars"],
            "tp_reason":  trade_plan.get("reason", ""),  # ← reason จาก risk_manager
        })

        if sim["result"] in ("WIN", "LOSS"):
            in_position = False
        else:
            skip_until_bar = (i + 1) + int(sim["bars"])

    wins   = sum(1 for t in trades if t["result"] == "WIN")
    losses = sum(1 for t in trades if t["result"] == "LOSS")
    closed = wins + losses
    wr     = round((wins / closed) * 100, 2) if closed > 0 else 0.0

    return {
        "symbol":         symbol,
        "trades":         len(trades),
        "wins":           wins,
        "losses":         losses,
        "winrate":        wr,
        "skipped":        dict(skipped),
        "invalid_reasons": dict(invalid_reasons),
        "trades_detail":  trades,
    }


def run_all_filter_tests(symbols: List[str], interval="1d", limit=1000):
    """รันทีละ filter: ปิดทีละตัว แล้วเทียบกับ baseline"""

    filter_names = list(FLAGS.keys())

    # --- Baseline (ทุก filter เปิด) ---
    print("=" * 70)
    print("BASELINE (ทุก filter เปิด)")
    print("=" * 70)
    for k in filter_names:
        FLAGS[k] = True

    baseline = {}
    for s in symbols:
        r = run_backtest_with_flags(s, interval=interval, limit=limit)
        baseline[s] = r
        print(f"  {s:<12} trades={r['trades']:<5} wins={r['wins']:<4} wr={r['winrate']}%")

    total_base = sum(r["trades"] for r in baseline.values())
    wr_base    = round(sum(r["wins"] for r in baseline.values()) /
                       max(sum(r["wins"] + r["losses"] for r in baseline.values()), 1) * 100, 2)
    print(f"\n  รวม trades={total_base}  winrate={wr_base}%")

    # --- ปิดทีละ filter ---
    print()
    print("=" * 70)
    print("เทียบผลเมื่อปิดตัวกรองทีละตัว")
    print("=" * 70)
    print(f"{'FILTER':<25} {'TRADES':>7} {'DIFF':>7} {'WINRATE':>9} {'DIFF_WR':>9}")
    print("-" * 62)

    for fname in filter_names:
        # reset ทุก flag เป็น True แล้วปิดแค่ตัวนี้
        for k in filter_names:
            FLAGS[k] = True
        FLAGS[fname] = False   # ← ปิดตัวนี้

        total_trades = 0
        total_wins   = 0
        total_closed = 0

        for s in symbols:
            r = run_backtest_with_flags(s, interval=interval, limit=limit)
            total_trades += r["trades"]
            total_wins   += r["wins"]
            total_closed += r["wins"] + r["losses"]

        wr   = round((total_wins / max(total_closed, 1)) * 100, 2)
        diff = total_trades - total_base
        dwr  = round(wr - wr_base, 2)

        diff_str = f"+{diff}" if diff > 0 else str(diff)
        dwr_str  = f"+{dwr}" if dwr > 0 else str(dwr)

        print(f"  OFF: {fname:<20} {total_trades:>7} {diff_str:>7} {wr:>8}% {dwr_str:>8}%")

    # reset กลับ
    for k in filter_names:
        FLAGS[k] = True
    print()
    print("✅ เสร็จ — ดูคอลัมน์ DIFF: + = เทรดเพิ่ม, - = เทรดลด")
    print("          ดูคอลัมน์ DIFF_WR: + = winrate ดีขึ้น, - = แย่ลง")


# ================================================================
# Main
# ================================================================
if __name__ == "__main__":
    from app.config.wave_settings import SYMBOLS

    # ทดสอบแค่ 3 เหรียญก่อนถ้าต้องการเร็ว
    test_symbols = SYMBOLS[:3]

    print(f"ทดสอบกับ: {test_symbols}")
    print(f"FLAGS: {FLAGS}")
    print()

    run_all_filter_tests(test_symbols, interval="1d", limit=500)