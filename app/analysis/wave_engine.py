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

def analyze_symbol(symbol: str):
    # 1) Fetch data (1D)
    df = fetch_ohlcv(symbol, interval=TIMEFRAME, limit=BARS)
    df = drop_unclosed_candle(df)

    if len(df) < 250:  # ต้องพอสำหรับ EMA200
        return None

    # 1.5) Add indicators (1D)
    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)

    last_close = float(df["close"].iloc[-1])
    current_price = last_close
    close_today = float(df["close"].iloc[-1])
    close_yesterday = float(df["close"].iloc[-2]) if len(df) >= 2 else None

    macro_trend = trend_filter_ema(df)  # BULL/BEAR/NEUTRAL (1D)
    rsi14 = float(df["rsi14"].iloc[-1])
    is_vol_spike = bool(volume_spike(df, length=20, multiplier=1.5))

    # 1.8) MTF summary (1W permit / 4H confirm)  ✅ ใช้งานจริงใน pipeline
    mtf = get_mtf_summary(symbol) or {}
    weekly_permit_long = bool(mtf.get("weekly_permit_long", True))
    weekly_permit_short = bool(mtf.get("weekly_permit_short", True))
    h4_confirm_long = bool(mtf.get("h4_confirm_long", False))
    h4_confirm_short = bool(mtf.get("h4_confirm_short", False))

    # 2) Pivot detection (1D)
    pivots = find_fractal_pivots(df)
    pivots = filter_pivots(pivots, min_pct_move=1.5)
    wave_label = label_pivot_chain(pivots)

    if len(pivots) < 4:
        return {
            "symbol": symbol,
            "price": current_price,
            "close_today": close_today,
            "close_yesterday": close_yesterday,
            "macro_trend": macro_trend,
            "rsi14": rsi14,
            "volume_spike": is_vol_spike,
            "mtf": mtf,
            "scenarios": [],
            "message": "โครงสร้างยังไม่ชัด",
            "wave_label": wave_label,
        }

    # 3) Build scenarios (top 3) (1D)
    scenarios = build_scenarios(
        pivots,
        macro_trend=macro_trend,
        rsi14=rsi14,
        volume_spike=is_vol_spike
    )

    # 3.5) Context gate
    regime = detect_market_regime(df)
    macro_bias = compute_macro_bias(regime, rsi14=rsi14)

    gated_scenarios = []
    for sc in (scenarios or []):
        gated = apply_context_gate(
            scenario=sc,
            macro_bias=macro_bias,
            min_confidence=55.0,
        )
        if isinstance(gated, dict) and gated.get("direction"):
            gated_scenarios.append(gated)

    scenarios = gated_scenarios

    results = []

    # 4) Build trade plan per scenario  ✅ ใส่ MTF gate ตรงนี้จริง
    for scenario in scenarios:
        direction = (scenario.get("direction") or "").upper()
        if not direction:
            continue

        # --- MTF Gate ---
        if direction == "LONG" and not weekly_permit_long:
            continue
        if direction == "SHORT" and not weekly_permit_short:
            continue

        mtf_ok = True
        if direction == "LONG" and not h4_confirm_long:
            mtf_ok = False
        if direction == "SHORT" and not h4_confirm_short:
            mtf_ok = False

        # Trend filter (1D macro)
        if not allow_direction(macro_trend, direction):
            continue

        # RSI filter (1D momentum)
        if direction == "LONG" and rsi14 < 50:
            continue
        if direction == "SHORT" and rsi14 > 50:
            continue

        # SNIPER FILTER
        if float(scenario.get("confidence", 0)) < 70:
            continue

        trade_plan = build_trade_plan(
            scenario,
            current_price=current_price,
            min_rr=3.0
        )

        if not trade_plan.get("triggered"):
            continue

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
            "type": scenario["type"],
            "phase": scenario["phase"],
            "direction": direction,
            "probability": scenario.get("probability"),
            "confidence": scenario.get("confidence"),
            "mtf_ok": mtf_ok,
            "trade_plan": trade_plan,
            "reasons": scenario.get("reasons", []),
        })

    msg = None
    if scenarios and not results:
        msg = (
            f"โดนกรองด้วย MTF/Trend/RSI "
            f"(1D={macro_trend}, rsi14={rsi14:.1f}, "
            f"1Wpermit(L/S)={weekly_permit_long}/{weekly_permit_short}, "
            f"4Hconfirm(L/S)={h4_confirm_long}/{h4_confirm_short})"
        )

    return {
        "symbol": symbol,
        "price": current_price,
        "close_today": close_today,
        "close_yesterday": close_yesterday,
        "macro_trend": macro_trend,
        "rsi14": rsi14,
        "volume_spike": is_vol_spike,
        "mtf": mtf,
        "scenarios": results,
        "message": msg,
        "wave_label": wave_label,
    }