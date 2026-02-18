from typing import Dict, List
import pandas as pd

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

def _simulate_one_trade(df: pd.DataFrame, start_i: int, direction: str, entry: float, sl: float, tp1: float, tp2: float, tp3: float) -> Dict:
    """
    เดินแท่งจาก start_i ไปข้างหน้า จนเจอ SL หรือ TP3
    หมายเหตุ: ใช้ high/low เพื่อเช็คการชนระดับ (simple backtest)
    """
    for i in range(start_i, len(df)):
        high = float(df["high"].iloc[i])
        low = float(df["low"].iloc[i])

        if direction == "LONG":
            # SL ก่อน (conservative)
            if low <= sl:
                return {"result": "LOSS", "exit": sl, "bars": i - start_i}
            if high >= tp3:
                return {"result": "WIN", "exit": tp3, "bars": i - start_i}

        else:  # SHORT
            if high >= sl:
                return {"result": "LOSS", "exit": sl, "bars": i - start_i}
            if low <= tp3:
                return {"result": "WIN", "exit": tp3, "bars": i - start_i}

    return {"result": "OPEN", "exit": None, "bars": len(df) - start_i}


def backtest_symbol(symbol: str, interval: str = "1d", limit: int = 1000, min_pct_move: float = 1.5, min_rr: float = 2.0) -> Dict:
    """
    Backtest แบบง่าย:
    - ใช้ข้อมูลย้อนหลัง limit แท่ง
    - ทุกแท่ง (หลังมีข้อมูลพอ) จะลองสร้าง scenario จาก pivot ล่าสุด
    - ถ้า trade_plan valid + triggered (close confirm) → เปิด 1 เทรด
    - 1 เทรดจบเมื่อ SL หรือ TP3
    - ไม่มีการเปิดซ้อน (strict)
    """
    df = fetch_ohlcv(symbol, interval=interval, limit=limit)
    df = drop_unclosed_candle(df)

    if len(df) < 250:
        return {
            "symbol": symbol,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "open": 0,
            "winrate": 0.0,
            "buckets": {
                "conf>=60": {"trades": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0.0},
                "conf>=70": {"trades": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0.0},
                "conf>=80": {"trades": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0.0},
            },
        }

    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)

    trades: List[Dict] = []
    in_position = False
    skip_until_bar = 0      # ✅ กัน bar ซ้อนกันกรณี OPEN
    start_bar = 250

    for i in range(start_bar, len(df) - 1):
        if in_position or i < skip_until_bar:   # ✅ เพิ่ม skip_until_bar
            continue

        sub = df.iloc[: i + 1].copy()

        macro_trend = trend_filter_ema(sub)
        rsi14 = float(sub["rsi14"].iloc[-1])
        is_vol_spike = bool(volume_spike(sub, length=20, multiplier=1.5))
        last_close = float(sub["close"].iloc[-1])

        pivots = find_fractal_pivots(sub)
        pivots = filter_pivots(pivots, min_pct_move=min_pct_move)
        if len(pivots) < 4:
            continue

        scenarios = build_scenarios(
            pivots,
            macro_trend=macro_trend,
            rsi14=rsi14,
            volume_spike=is_vol_spike
        )
        if not scenarios:
            continue

        regime = detect_market_regime(sub)
        macro_bias = compute_macro_bias(regime, rsi14=rsi14)
        gated = []
        for sc in scenarios:
            r = apply_context_gate(sc, macro_bias=macro_bias, min_confidence=55.0)
            if r:
                gated.append(r)
        if not gated:
            continue
        scenarios = gated

        sc = scenarios[0]
        direction = sc["direction"]

        if not allow_direction(macro_trend, direction):
            continue

        if direction == "LONG" and rsi14 < 50:
            continue
        if direction == "SHORT" and rsi14 > 50:
            continue

        trade_plan = build_trade_plan(sc, current_price=last_close, min_rr=min_rr)
        if not trade_plan.get("valid"):
            continue

        entry = float(trade_plan["entry"])

        triggered = False
        if direction == "LONG" and last_close > entry:
            triggered = True
        if direction == "SHORT" and last_close < entry:
            triggered = True
        if not triggered:
            continue

        in_position = True

        sim = _simulate_one_trade(
            df=df,
            start_i=i + 1,
            direction=direction,
            entry=entry,
            sl=float(trade_plan["sl"]),
            tp1=float(trade_plan["tp1"]),
            tp2=float(trade_plan["tp2"]),
            tp3=float(trade_plan["tp3"]),
        )

        trades.append({
            "symbol": symbol,
            "bar_index": i,
            "direction": direction,
            "entry": entry,
            "sl": float(trade_plan["sl"]),
            "tp3": float(trade_plan["tp3"]),
            "confidence": float(sc.get("confidence") or sc.get("score") or 0),
            "result": sim["result"],
            "bars_held": sim["bars"],
        })

        # ✅ indent ถูก + set skip_until_bar กรณี OPEN
        if sim["result"] in ("WIN", "LOSS"):
            in_position = False
        else:
            skip_until_bar = (i + 1) + int(sim["bars"])
            in_position = False

    wins = sum(1 for t in trades if t["result"] == "WIN")
    losses = sum(1 for t in trades if t["result"] == "LOSS")
    opens = sum(1 for t in trades if t["result"] == "OPEN")
    total_closed = wins + losses
    winrate = round((wins / total_closed) * 100, 2) if total_closed > 0 else 0.0
    conf_values = [float(t.get("confidence") or 0) for t in trades]
    conf_min = round(min(conf_values), 2) if conf_values else 0.0
    conf_max = round(max(conf_values), 2) if conf_values else 0.0
    conf_avg = round(sum(conf_values) / len(conf_values), 2) if conf_values else 0.0

    # ---- Confidence buckets ----
    def _bucket_stats(min_conf: float) -> Dict:
        bucket = [t for t in trades if float(t.get("confidence") or 0) >= min_conf]
        w = sum(1 for t in bucket if t["result"] == "WIN")
        l = sum(1 for t in bucket if t["result"] == "LOSS")
        o = sum(1 for t in bucket if t["result"] == "OPEN")
        closed = w + l
        wr = round((w / closed) * 100, 2) if closed > 0 else 0.0
        return {"trades": len(bucket), "wins": w, "losses": l, "open": o, "winrate": wr}

    buckets = {
        "conf>=60": _bucket_stats(60),
        "conf>=70": _bucket_stats(70),
        "conf>=80": _bucket_stats(80),
    }

    return {
        "symbol": symbol,
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "open": opens,
        "winrate": winrate,
        "conf_min": conf_min,
        "conf_max": conf_max,
        "conf_avg": conf_avg,
        "buckets": buckets,
    }


def _r_multiple(direction: str, entry: float, sl: float, tp3: float, result: str) -> float:
    """
    คิดผลเป็นหน่วย R
    - LOSS = -1R
    - WIN  = +RR_tp3 (เช่น 2R ถ้า tp3/SL ระยะเท่ากับ 2 เท่าของความเสี่ยง)
    """
    risk = abs(entry - sl)
    if risk <= 0:
        return 0.0

    rr_tp3 = abs(tp3 - entry) / risk

    if result == "LOSS":
        return -1.0
    if result == "WIN":
        return float(rr_tp3)
    return 0.0


def backtest_symbol_trades(
    symbol: str,
    interval: str = "1d",
    limit: int = 1000,
    min_pct_move: float = 1.5,
    min_rr: float = 2.0,
    min_confidence: float = 0.0,
) -> Dict:
    """
    เหมือน backtest_symbol แต่คืน trades list พร้อม entry/exit time + R multiple
    """
    df = fetch_ohlcv(symbol, interval=interval, limit=limit)
    df = drop_unclosed_candle(df)

    if len(df) < 250:
        return {"symbol": symbol, "trades": []}

    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)

    trades: List[Dict] = []
    in_position = False
    skip_until_bar = 0      # ✅ กัน bar ซ้อนกันกรณี OPEN
    start_bar = 250

    for i in range(start_bar, len(df) - 1):
        if in_position or i < skip_until_bar:   # ✅ เพิ่ม skip_until_bar
            continue

        sub = df.iloc[: i + 1].copy()

        macro_trend = trend_filter_ema(sub)
        rsi14 = float(sub["rsi14"].iloc[-1])
        is_vol_spike = bool(volume_spike(sub, length=20, multiplier=1.5))
        last_close = float(sub["close"].iloc[-1])

        pivots = find_fractal_pivots(sub)
        pivots = filter_pivots(pivots, min_pct_move=min_pct_move)
        if len(pivots) < 4:
            continue

        scenarios = build_scenarios(pivots, macro_trend=macro_trend, rsi14=rsi14, volume_spike=is_vol_spike)
        if not scenarios:
            continue

        regime = detect_market_regime(sub)
        macro_bias = compute_macro_bias(regime, rsi14=rsi14)
        gated = []
        for sc in scenarios:
            r = apply_context_gate(sc, macro_bias=macro_bias, min_confidence=55.0)
            if r:
                gated.append(r)
        if not gated:
            continue
        scenarios = gated

        sc = scenarios[0]
        direction = sc["direction"]

        if not allow_direction(macro_trend, direction):
            continue
        if direction == "LONG" and rsi14 < 50:
            continue
        if direction == "SHORT" and rsi14 > 50:
            continue

        conf = float(sc.get("confidence") or sc.get("score") or 0)
        if conf < float(min_confidence):
            continue

        trade_plan = build_trade_plan(sc, current_price=last_close, min_rr=min_rr)
        if not trade_plan.get("valid"):
            continue

        entry = float(trade_plan["entry"])

        # close confirm
        triggered = False
        if direction == "LONG" and last_close > entry:
            triggered = True
        if direction == "SHORT" and last_close < entry:
            triggered = True
        if not triggered:
            continue

        in_position = True

        start_i = i + 1
        sim = _simulate_one_trade(
            df=df,
            start_i=start_i,
            direction=direction,
            entry=entry,
            sl=float(trade_plan["sl"]),
            tp1=float(trade_plan["tp1"]),
            tp2=float(trade_plan["tp2"]),
            tp3=float(trade_plan["tp3"]),
        )

        # หา exit index/time จาก bars ที่คืนมา
        exit_index = None
        exit_time = None
        if sim["result"] in ("WIN", "LOSS"):
            exit_index = start_i + int(sim["bars"])
            if 0 <= exit_index < len(df):
                exit_time = df["open_time"].iloc[exit_index]

        entry_time = df["open_time"].iloc[i]  # วันที่ trigger (แท่งที่ปิดยืนยัน)

        r = _r_multiple(direction, entry, float(trade_plan["sl"]), float(trade_plan["tp3"]), sim["result"])

        trades.append({
            "symbol": symbol,
            "entry_index": i,
            "entry_time": entry_time,
            "exit_index": exit_index,
            "exit_time": exit_time,
            "direction": direction,
            "confidence": conf,
            "entry": entry,
            "sl": float(trade_plan["sl"]),
            "tp3": float(trade_plan["tp3"]),
            "result": sim["result"],
            "r_multiple": r,
        })

        # ✅ set skip_until_bar กรณี OPEN
        if sim["result"] in ("WIN", "LOSS"):
            in_position = False
        else:
            skip_until_bar = (i + 1) + int(sim["bars"])
            in_position = False

    return {"symbol": symbol, "trades": trades}


def portfolio_simulator(
    symbols: List[str],
    interval: str = "1d",
    limit: int = 1000,
    min_pct_move: float = 1.5,
    min_rr: float = 2.0,
    min_confidence: float = 60.0,
) -> Dict:
    """
    Portfolio simulator แบบง่าย:
    - รวมเทรดของทุกเหรียญ (filtered ด้วย min_confidence)
    - จัดเรียงตาม entry_time
    - คิด equity เป็นผลรวม R (1R ต่อเทรด)
    - คำนวณ Max Drawdown จาก equity curve
    """
    all_trades: List[Dict] = []

    for s in symbols:
        res = backtest_symbol_trades(
            s,
            interval=interval,
            limit=limit,
            min_pct_move=min_pct_move,
            min_rr=min_rr,
            min_confidence=min_confidence,
        )
        all_trades.extend(res["trades"])

    # เรียงตามเวลาเข้า
    all_trades.sort(key=lambda x: x["entry_time"])

    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    closed = [t for t in all_trades if t["result"] in ("WIN", "LOSS")]
    wins = sum(1 for t in closed if t["result"] == "WIN")
    losses = sum(1 for t in closed if t["result"] == "LOSS")
    total = len(closed)
    winrate = round((wins / total) * 100, 2) if total > 0 else 0.0

    curve = []
    for t in closed:
        equity += float(t["r_multiple"])
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        curve.append(equity)

    return {
        "symbols": symbols,
        "min_confidence": float(min_confidence),
        "trades": total,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "equity_R": round(equity, 2),
        "max_drawdown_R": round(max_dd, 2),
    }


if __name__ == "__main__":
    # ✅ ชุดที่แนะนำจากผล backtest ของคุณ
    symbols = ["BTCUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT", "TRXUSDT", "DOGEUSDT"]

    # Portfolio (conf>=60)
    res = portfolio_simulator(symbols, interval="1d", limit=1000, min_confidence=60)
    print(res)

    # เผื่ออยากดูเข้มขึ้น
    res2 = portfolio_simulator(symbols, interval="1d", limit=1000, min_confidence=70)
    print(res2)