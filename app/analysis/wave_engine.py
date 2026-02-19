from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from app.data.binance_fetcher import fetch_ohlcv, drop_unclosed_candle
from app.analysis.pivot import find_fractal_pivots, filter_pivots
from app.analysis.wave_scenarios import build_scenarios
from app.risk.risk_manager import build_trade_plan

from app.config.wave_settings import BARS, TIMEFRAME, MIN_RR

from app.indicators.ema import add_ema
from app.indicators.rsi import add_rsi
from app.indicators.atr import add_atr
from app.indicators.volume import add_volume_ma, volume_spike
from app.indicators.trend_filter import trend_filter_ema, allow_direction

from app.analysis.wave_labeler import label_pivot_chain
from app.analysis.context_gate import apply_context_gate
from app.analysis.market_regime import detect_market_regime
from app.analysis.macro_bias import compute_macro_bias
from app.analysis.multi_tf import get_mtf_summary

# NOTE: ไฟล์/โมดูลนี้อาจยังไม่ถูกสร้างในบาง branch
# เพื่อกันระบบพัง ให้มี fallback แบบง่าย
try:
    from app.analysis.trend_detector import detect_market_mode  # type: ignore
except Exception:

    def detect_market_mode(df: pd.DataFrame) -> str:
        """Fallback: ถ้าไม่มี trend_detector ให้ map จาก market_regime"""
        try:
            reg = (detect_market_regime(df) or {}).get("regime", "CHOP").upper()
            if "SIDE" in reg or "RANGE" in reg:
                return "SIDEWAY"
            return "TREND"
        except Exception:
            return "TREND"


def _safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _range_levels(df: pd.DataFrame, lookback: int = 60) -> Dict:
    """คำนวณกรอบ sideway แบบง่ายจาก lookback ล่าสุด"""
    if df is None or len(df) < max(lookback, 20):
        return {"range_low": None, "range_high": None, "atr": None}

    sub = df.iloc[-lookback:].copy()
    range_low = _safe_float(sub["low"].min(), 0.0)
    range_high = _safe_float(sub["high"].max(), 0.0)

    atr = None
    if "atr14" in sub.columns:
        atr = _safe_float(sub["atr14"].iloc[-1], 0.0)

    return {
        "range_low": float(range_low) if range_low else None,
        "range_high": float(range_high) if range_high else None,
        "atr": float(atr) if atr else None,
    }


def run_sideway_engine(symbol: str, df: pd.DataFrame, base: Dict) -> Dict:
    """
    SIDEWAY ENGINE (v0): mean-reversion ในกรอบ

    เงื่อนไขเข้าแบบง่าย:
    - LONG: ราคาใกล้ range_low + buffer และ RSI ต่ำ
    - SHORT: ราคาใกล้ range_high - buffer และ RSI สูง
    """
    base = dict(base or {})

    price = _safe_float(base.get("price"), 0.0)
    rsi14 = _safe_float(base.get("rsi14"), 50.0)

    lv = _range_levels(df, lookback=60)
    range_low = lv.get("range_low")
    range_high = lv.get("range_high")
    atr = lv.get("atr")

    base["sideway"] = {
        "range_low": range_low,
        "range_high": range_high,
        "atr": atr,
        "lookback": 60,
    }

    # ถ้าข้อมูลไม่พอ -> คืนแบบไม่ยิงสัญญาณ
    if not range_low or not range_high or range_high <= range_low:
        base["scenarios"] = []
        base["message"] = "SIDEWAY: ข้อมูลยังไม่พอคำนวณกรอบ"
        return base

    # buffer กันหลอก: ใช้ ATR ถ้ามี ไม่งั้นใช้ 0.5% ของราคา
    buffer = float(atr) * 0.5 if atr and atr > 0 else float(price) * 0.005

    near_support = price <= (range_low + buffer)
    near_resist = price >= (range_high - buffer)

    scenarios: List[Dict] = []

    # LONG near support + RSI low
    if near_support and rsi14 <= 45:
        sc = {
            "type": "SIDEWAY_RANGE",
            "phase": "MEAN_REVERT",
            "direction": "LONG",
            "probability": 0.0,
            "confidence": 65.0,
            "reasons": [
                f"Near range low ({range_low:,.2f})",
                f"RSI14 low ({rsi14:.1f})",
            ],
        }
        plan = build_trade_plan(sc, current_price=price, min_rr=2.0)
        sc["trade_plan"] = plan
        scenarios.append(sc)

    # SHORT near resist + RSI high
    if near_resist and rsi14 >= 55:
        sc = {
            "type": "SIDEWAY_RANGE",
            "phase": "MEAN_REVERT",
            "direction": "SHORT",
            "probability": 0.0,
            "confidence": 65.0,
            "reasons": [
                f"Near range high ({range_high:,.2f})",
                f"RSI14 high ({rsi14:.1f})",
            ],
        }
        plan = build_trade_plan(sc, current_price=price, min_rr=2.0)
        sc["trade_plan"] = plan
        scenarios.append(sc)

    base["scenarios"] = scenarios

    if scenarios:
        base["message"] = (
            f"SIDEWAY: พบ setup ในกรอบ ({range_low:,.2f} - {range_high:,.2f})"
        )
    else:
        base["message"] = (
            f"SIDEWAY: ยังไม่เข้าเงื่อนไข (กรอบ {range_low:,.2f} - {range_high:,.2f})"
        )

    return base


def analyze_symbol(symbol: str) -> Optional[Dict]:
    # 1) Fetch data (1D)
    df = fetch_ohlcv(symbol, interval=TIMEFRAME, limit=BARS)
    df = drop_unclosed_candle(df)

    if df is None or len(df) < 250:  # ต้องพอสำหรับ EMA200
        return None

    # 1.5) Add indicators (1D)
    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)

    last_close = float(df["close"].iloc[-1])
    current_price = last_close
    close_today = last_close
    close_yesterday = float(df["close"].iloc[-2]) if len(df) >= 2 else None

    macro_trend = trend_filter_ema(df)  # BULL/BEAR/NEUTRAL (1D)
    rsi14 = float(df["rsi14"].iloc[-1])
    is_vol_spike = bool(volume_spike(df, length=20, multiplier=1.5))

    # 1.6) Trend / Sideway mode
    mode = detect_market_mode(df)
    size_mult = 1.0 if mode == "TREND" else 0.5

    # 1.8) MTF summary (1W permit / 4H confirm)
    mtf = get_mtf_summary(symbol) or {}
    weekly_permit_long = bool(mtf.get("weekly_permit_long", True))
    weekly_permit_short = bool(mtf.get("weekly_permit_short", True))
    h4_confirm_long = bool(mtf.get("h4_confirm_long", False))
    h4_confirm_short = bool(mtf.get("h4_confirm_short", False))

    base = {
        "symbol": symbol,
        "price": current_price,
        "close_today": close_today,
        "close_yesterday": close_yesterday,
        "macro_trend": macro_trend,
        "rsi14": rsi14,
        "volume_spike": is_vol_spike,
        "mtf": mtf,
        "mode": mode,
        "position_size_mult": size_mult,
    }

    # SIDEWAY -> engine แยก
    if mode == "SIDEWAY":
        return run_sideway_engine(symbol, df, base)

    # 2) Pivot detection (1D)
    pivots = find_fractal_pivots(df)
    pivots = filter_pivots(pivots, min_pct_move=1.5)
    wave_label = label_pivot_chain(pivots)

    if len(pivots) < 4:
        out = dict(base)
        out.update({
            "scenarios": [],
            "message": "โครงสร้างยังไม่ชัด",
            "wave_label": wave_label,
            "sideway": None,
        })
        return out

    # 3) Build scenarios (top 3) (1D)
    scenarios = build_scenarios(
        pivots,
        macro_trend=macro_trend,
        rsi14=rsi14,
        volume_spike=is_vol_spike,
    )

    # 3.5) Context gate — ✅ FIX: ใช้ compute_macro_bias จริง ไม่ hardcode
    regime = detect_market_regime(df)
    macro_bias = compute_macro_bias(regime, rsi14=rsi14)

    gated_scenarios: List[Dict] = []
    for sc in (scenarios or []):
        gated = apply_context_gate(
            scenario=sc,
            macro_bias=macro_bias,
            min_confidence=55.0,
        )
        if isinstance(gated, dict) and gated.get("direction"):
            gated_scenarios.append(gated)

    scenarios = gated_scenarios

    results: List[Dict] = []

    # 4) Build trade plan per scenario
    for scenario in (scenarios or []):
        direction = (scenario.get("direction") or "").upper()
        if not direction:
            continue

        # --- MTF Gate (weekly permit) ---
        if direction == "LONG" and not weekly_permit_long:
            continue
        if direction == "SHORT" and not weekly_permit_short:
            continue

        # --- MTF Gate (4H confirm) ---
        mtf_ok = True
        if direction == "LONG" and not h4_confirm_long:
            mtf_ok = False
        if direction == "SHORT" and not h4_confirm_short:
            mtf_ok = False

        # ✅ FIX: เช็ค mtf_ok ก่อน build_trade_plan (เดิมเช็คผิดที่)
        if not mtf_ok:
            continue

        # Trend filter (1D macro)
        if not allow_direction(macro_trend, direction):
            continue

        # RSI filter (1D momentum)
        if direction == "LONG" and rsi14 < 50:
            continue
        if direction == "SHORT" and rsi14 > 50:
            continue

        # SNIPER FILTER
        if float(scenario.get("confidence") or 0) < 70:
            continue

        trade_plan = build_trade_plan(
            scenario,
            current_price=current_price,
            min_rr=float(MIN_RR) if MIN_RR else 3.0,
        )

        # Close-confirm trigger
        entry = trade_plan.get("entry")
        if entry is not None:
            entry = float(entry)
            if direction == "LONG" and last_close <= entry:
                trade_plan["triggered"] = False
            elif direction == "SHORT" and last_close >= entry:
                trade_plan["triggered"] = False
            else:
                trade_plan["triggered"] = True
        else:
            trade_plan["triggered"] = False

        trade_plan["volume_ok"] = is_vol_spike

        results.append({
            "type": scenario.get("type"),
            "phase": scenario.get("phase"),
            "direction": direction,
            "probability": scenario.get("probability"),
            "confidence": scenario.get("confidence"),
            "context_score": scenario.get("context_score"),
            "mtf_ok": mtf_ok,
            "trade_plan": trade_plan,
            "reasons": scenario.get("reasons", []),
        })

    msg = None
    if scenarios and not results:
        msg = (
            f"โดนกรองด้วย MTF/Trend/RSI/SNIPER "
            f"(1D={macro_trend}, rsi14={rsi14:.1f}, "
            f"1Wpermit(L/S)={weekly_permit_long}/{weekly_permit_short}, "
            f"4Hconfirm(L/S)={h4_confirm_long}/{h4_confirm_short})"
        )

    out = dict(base)
    out.update({
        "scenarios": results,
        "message": msg,
        "wave_label": wave_label,
        "sideway": None,
    })
    return out