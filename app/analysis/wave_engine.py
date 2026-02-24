from __future__ import annotations

from typing import Dict, List, Optional
import logging
logger = logging.getLogger(__name__)

import pandas as pd
import os
import requests as req

from app.data.binance_fetcher import fetch_ohlcv, drop_unclosed_candle
from app.analysis.pivot import find_fractal_pivots, filter_pivots
from app.analysis.wave_scenarios import build_scenarios
from app.risk.risk_manager import build_trade_plan

from app.indicators.ema import add_ema
from app.indicators.rsi import add_rsi
from app.indicators.atr import add_atr
from app.indicators.volume import add_volume_ma, volume_spike
from app.indicators.trend_filter import trend_filter_ema

from app.analysis.wave_labeler import label_pivot_chain
from app.analysis.context_gate import apply_context_gate
from app.analysis.market_regime import detect_market_regime
from app.analysis.macro_bias import compute_macro_bias
from app.analysis.multi_tf import get_mtf_summary
from app.analysis.zones import build_zones_from_pivots, nearest_support_resist
from app.analysis.trend_detector import detect_market_mode
from app.config.wave_settings import (
    BARS,
    TIMEFRAME,
    MIN_RR,
    MIN_CONFIDENCE_LIVE,
    ABC_CONFIRM_BUFFER,
)


def _send_log(msg: str) -> None:
    try:
        vps_url = os.getenv("VPS_URL", "")
        exec_token = os.getenv("EXEC_TOKEN", "")
        if vps_url:
            req.post(
                f"{vps_url}/log",
                json={"msg": msg},
                headers={"X-EXEC-TOKEN": exec_token},
                timeout=5,
            )
    except Exception:
        pass

def _safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

# ── ลบ _fallback_entry_from_pivots ──────────────────────────────────────────
# เหตุผล: ใช้คู่กับ _force_minimal_trade_plan เท่านั้น ซึ่งถูกลบออกแล้ว
# ถ้า build_trade_plan คืน entry=None → valid=False → BLOCKED ตามปกติ

# ── ลบ _force_minimal_trade_plan ────────────────────────────────────────────
# เหตุผล: bypass valid=True โดยไม่ผ่านการคำนวณ RR จริง
#         ทำให้ F_RR_VALID ไม่มีผลเลยใน Live
#         ลบออกเพื่อให้ RR filter ทำงานได้ตามปกติ

# ── ลบ _ensure_basic_risk_levels ────────────────────────────────────────────
# เหตุผล: ไม่ถูกเรียกใช้ที่ไหนใน codebase (dead code)

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
    """
    base = dict(base or {})

    price = _safe_float(base.get("price"), 0.0)
    rsi14 = _safe_float(base.get("rsi14"), 50.0)
    weekly_permit_long = bool(base.get("weekly_permit_long", True))
    weekly_permit_short = bool(base.get("weekly_permit_short", True))

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

    if not range_low or not range_high or range_high <= range_low:
        base["scenarios"] = []
        base["message"] = "SIDEWAY: ข้อมูลยังไม่พอคำนวณกรอบ"
        return base

    buffer = float(atr) * 0.5 if atr and atr > 0 else float(price) * 0.005

    near_support = price <= (range_low + buffer)
    near_resist = price >= (range_high - buffer)

    scenarios: List[Dict] = []

    if near_support and rsi14 <= 45 and weekly_permit_long:
        sc = {
            "type": "SIDEWAY_RANGE",
            "phase": "MEAN_REVERT",
            "direction": "LONG",
            "probability": 0.0,
            "confidence": 65.0,
            "range_low": range_low,
            "range_high": range_high,
            "atr": atr,
            "reasons": [
                f"Near range low ({range_low:,.2f})",
                f"RSI14 low ({rsi14:.1f})",
            ],
        }
        plan = build_trade_plan(sc, current_price=price, min_rr=2.0)
        plan["triggered"] = True
        sc["trade_plan"] = plan
        scenarios.append(sc)

    if near_resist and rsi14 >= 55 and weekly_permit_short:
        sc = {
            "type": "SIDEWAY_RANGE",
            "phase": "MEAN_REVERT",
            "direction": "SHORT",
            "probability": 0.0,
            "confidence": 65.0,
            "range_low": range_low,
            "range_high": range_high,
            "atr": atr,
            "reasons": [
                f"Near range high ({range_high:,.2f})",
                f"RSI14 high ({rsi14:.1f})",
            ],
        }
        plan = build_trade_plan(sc, current_price=price, min_rr=2.0)
        plan["triggered"] = True
        sc["trade_plan"] = plan
        scenarios.append(sc)

    base["scenarios"] = scenarios

    if scenarios:
        base["message"] = f"SIDEWAY: พบ setup ในกรอบ ({range_low:,.2f} - {range_high:,.2f})"
    else:
        base["message"] = f"SIDEWAY: ยังไม่เข้าเงื่อนไข (กรอบ {range_low:,.2f} - {range_high:,.2f})"

    return base


def analyze_symbol(symbol: str) -> Optional[Dict]:
    df = fetch_ohlcv(symbol, interval=TIMEFRAME, limit=BARS)
    df = drop_unclosed_candle(df)

    if df is None or len(df) < 250:
        return None

    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)

    # --- ATR Gate (align with backtest): ต้องเป็น compression ก่อน ---
    atr = float(df["atr14"].iloc[-1])
    atr_ma50 = float(df["atr14"].rolling(50).mean().iloc[-1]) if len(df) >= 50 else 0.0

    if atr_ma50 > 0 and atr >= atr_ma50:
        # ตลาดยังไม่ compress → ไม่เข้าเงื่อนไข (return base payload)
        return {
            "symbol": symbol,
            "price": float(df["close"].iloc[-1]),
            "scenarios": [],
            "message": "ATR_GATE: ตลาดยังไม่ compress",
            "mode": detect_market_mode(df),
            "macro_trend": trend_filter_ema(df),
            "rsi14": float(df["rsi14"].iloc[-1]),
            "volume_spike": False,
            "mtf": {},
            "wave_label": {"label": None, "matches": []},
            "sideway": None,
            "zones": [],
            "sr": {},
            "position_size_mult": 1.0,
        }

    last_close = float(df["close"].iloc[-1])
    current_price = last_close
    close_today = last_close
    close_yesterday = float(df["close"].iloc[-2]) if len(df) >= 2 else None

    macro_trend = trend_filter_ema(df)
    rsi14 = float(df["rsi14"].iloc[-1])
    is_vol_spike = bool(volume_spike(df, length=20, multiplier=1.5))

    mode = detect_market_mode(df)
    size_mult = 1.0 if mode == "TREND" else 0.5

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

    if mode == "SIDEWAY":
        base["weekly_permit_long"] = weekly_permit_long
        base["weekly_permit_short"] = weekly_permit_short
        return run_sideway_engine(symbol, df, base)

    pivots = find_fractal_pivots(df)
    pivots = filter_pivots(pivots, min_pct_move=1.5)
    wave_label = label_pivot_chain(pivots)

    zones = build_zones_from_pivots(df)
    sr = nearest_support_resist(zones, price=current_price)

    if len(pivots) < 4:
        out = dict(base)
        out.update({
            "scenarios": [],
            "message": "โครงสร้างยังไม่ชัด",
            "wave_label": wave_label,
            "sideway": None,
            "zones": zones if zones else [],
            "sr": sr if sr else {},
        })
        return out

    # --- สร้าง scenarios จาก pivots ---
    scenarios = build_scenarios(
        pivots,
        macro_trend=macro_trend,
        rsi14=rsi14,
        volume_spike=is_vol_spike,
    ) or []

    # --- Context gate ---
    regime = detect_market_regime(df)
    macro_bias = compute_macro_bias(regime, rsi14=rsi14)

    normalized: List[Dict] = []
    for sc in scenarios:
        # ✅ HARD BLOCK: fallback scenarios must never be tradable
        if sc.get("is_fallback"):
            sc2 = dict(sc)
            sc2["context_allowed"] = False
            sc2["context_reason"] = "fallback_scenario_blocked"
            normalized.append(sc2)
            continue

        gated = apply_context_gate(
            scenario=sc,
            macro_bias=macro_bias,
            min_confidence=MIN_CONFIDENCE_LIVE,
        )

        if isinstance(gated, dict) and gated.get("direction"):
            sc2 = dict(gated)
            sc2["context_allowed"] = True
            sc2["context_reason"] = None
            normalized.append(sc2)
        else:
            sc2 = dict(sc)
            sc2["context_allowed"] = False
            sc2["context_reason"] = "blocked_by_context_gate"
            normalized.append(sc2)

    scenarios = normalized

    results: List[Dict] = []

    for scenario in scenarios:
        direction = (scenario.get("direction") or "").upper()
        if not direction:
            continue

        # --- Weekly permit (HARD filter) ---
        weekly_ok = True
        if direction == "LONG" and not weekly_permit_long:
            weekly_ok = False
        if direction == "SHORT" and not weekly_permit_short:
            weekly_ok = False

        # --- 4H confirm (SOFT flag เท่านั้น) ---
        mtf_ok = True
        if direction == "LONG" and not h4_confirm_long:
            mtf_ok = False
        if direction == "SHORT" and not h4_confirm_short:
            mtf_ok = False

        context_allowed = bool(scenario.get("context_allowed", True))

        trade_plan = build_trade_plan(
            scenario,
            current_price=current_price,
            min_rr=float(MIN_RR) if MIN_RR else 3.0,
            sr=sr,
        )

        # FIX: ลบ _force_minimal_trade_plan ออกแล้ว
        # ถ้า build_trade_plan คืน entry=None หรือ valid=False
        # → trade_plan.valid=False → allowed_to_trade=False → BLOCKED
        # ให้ RR filter ทำงานตามปกติ

        # LIVE: Hard filter = weekly_ok + trade_plan.valid
        allowed_to_trade = bool(weekly_ok and trade_plan.get("valid") is True)

        # --- Trigger logic ---
        if not allowed_to_trade:
            trade_plan["triggered"] = False
        else:
            entry = trade_plan.get("entry")
            if entry is not None:
                entry = float(entry)
                stype = (scenario.get("type") or "").upper()
                if stype == "ABC_UP":
                    trade_plan["triggered"] = last_close > float(trade_plan["sl"]) * (1 + ABC_CONFIRM_BUFFER)
                elif stype == "ABC_DOWN":
                    trade_plan["triggered"] = last_close < float(trade_plan["sl"]) * (1 - ABC_CONFIRM_BUFFER)
                else:
                    if direction == "LONG" and last_close <= entry:
                        trade_plan["triggered"] = False
                    elif direction == "SHORT" and last_close >= entry:
                        trade_plan["triggered"] = False
                    else:
                        trade_plan["triggered"] = True
            else:
                trade_plan["triggered"] = False

        trade_plan["allowed_to_trade"] = allowed_to_trade
        trade_plan["weekly_ok"] = weekly_ok
        trade_plan["mtf_ok"] = mtf_ok
        trade_plan["context_allowed"] = context_allowed
        trade_plan["context_reason"] = scenario.get("context_reason")
        trade_plan["volume_ok"] = is_vol_spike

        _send_log(
            f"[{symbol}] dir={direction} conf={scenario.get('confidence')} "
            f"weekly_ok={weekly_ok} mtf_ok={mtf_ok} context={context_allowed} "
            f"valid={trade_plan.get('valid')} triggered={trade_plan.get('triggered')}"
        )

        # === STATUS / BLOCK REASON ===
        blocked = []
        if not weekly_ok:
            blocked.append("weekly_permit_block")
        if not mtf_ok:
            blocked.append("h4_confirm_block")
        if not context_allowed:
            blocked.append("context_gate_block")

        status = "READY" if (trade_plan.get("valid") and trade_plan.get("allowed_to_trade")) else "BLOCKED"

        results.append({
            "type": scenario.get("type"),
            "phase": scenario.get("phase"),
            "direction": direction,
            "probability": scenario.get("probability"),
            "confidence": scenario.get("confidence"),
            "context_score": scenario.get("context_score"),
            "weekly_ok": weekly_ok,
            "mtf_ok": mtf_ok,
            "context_allowed": context_allowed,
            "context_reason": scenario.get("context_reason"),
            "status": status,
            "blocked_reasons": blocked,
            "trade_plan": trade_plan,
            "reasons": scenario.get("reasons", []),
        })

        # Execute: เฉพาะ triggered จริงเท่านั้น
        if trade_plan.get("triggered"):
            try:
                vps_url = (os.getenv("VPS_URL", "") or "").strip()
                exec_token = (os.getenv("EXEC_TOKEN", "") or "").strip()

                if not vps_url.startswith("http"):
                    logger.info(f"[{symbol}] SKIP execute (VPS_URL not set)")
                    continue

                req.post(
                    f"{vps_url}/execute",
                    json={"symbol": symbol, "direction": direction, "trade_plan": trade_plan},
                    headers={"X-EXEC-TOKEN": exec_token},
                    timeout=10,
                )
                logger.info(f"[{symbol}] ส่ง signal ไป VPS สำเร็จ")
            except Exception as e:
                logger.error(f"[{symbol}] ส่ง signal ไป VPS ล้มเหลว: {e}")

    msg = None
    if scenarios and not results:
        msg = (
            f"ไม่มี scenario ที่สร้างได้ "
            f"(1D={macro_trend}, rsi14={rsi14:.1f})"
        )

    out = dict(base)
    out.update({
        "scenarios": results,
        "message": msg,
        "wave_label": wave_label,
        "sideway": None,
        "zones": zones if zones else [],
        "sr": sr if sr else {},
    })
    return out