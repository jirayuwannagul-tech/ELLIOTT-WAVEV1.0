from __future__ import annotations

import logging
from typing import Dict, List, Optional
from collections import Counter

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
from app.config.wave_settings import MIN_CONFIDENCE_BACKTEST, ABC_CONFIRM_BUFFER, MIN_CONFIDENCE_LIVE
from app.analysis.multi_tf import get_mtf_summary

logger = logging.getLogger(__name__)

# ---- constants ----
_START_BAR = 250
_EMPTY_BUCKETS = {
    "conf>=60": {"trades": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0.0},
    "conf>=70": {"trades": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0.0},
    "conf>=80": {"trades": 0, "wins": 0, "losses": 0, "open": 0, "winrate": 0.0},
}

INVALID_REASONS = Counter()

def _prepare_df(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    try:
        import sqlite3
        con = sqlite3.connect("data/market.db")
        cur = con.cursor()
        cur.execute(
            """
            SELECT ts, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol=? AND timeframe=?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (symbol, interval, int(limit)),
        )
        rows = cur.fetchall()
        con.close()

        if rows and len(rows) >= _START_BAR:
            rows = list(reversed(rows))
            df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
            df["open_time"] = pd.to_datetime(df["ts"], unit="s", utc=True)
            df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df = add_ema(df, lengths=(50, 200))
            df = add_rsi(df, length=14)
            df = add_atr(df, length=14)
            df = add_volume_ma(df, length=20)
            return df

    except Exception as e:
        logger.warning(f"[{symbol}] sqlite load failed -> fallback fetch ({e})")

    df = fetch_ohlcv(symbol, interval=interval, limit=limit)
    df = drop_unclosed_candle(df)
    if df is None or len(df) < _START_BAR:
        return None
    df = add_ema(df, lengths=(50, 200))
    df = add_rsi(df, length=14)
    df = add_atr(df, length=14)
    df = add_volume_ma(df, length=20)
    return df

def _simulate_one_trade(
    df: pd.DataFrame,
    start_i: int,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float,
) -> Dict:
    tp1_hit = False

    for i in range(start_i, len(df)):
        high = float(df["high"].iloc[i])
        low = float(df["low"].iloc[i])

        if direction == "LONG":
            if (not tp1_hit) and (high >= tp1):
                tp1_hit = True
                sl = entry
            if low <= sl:
                result = "BE" if tp1_hit else "LOSS"
                return {"result": result, "exit": sl, "bars": i - start_i}
            if high >= tp3:
                return {"result": "WIN", "exit": tp3, "bars": i - start_i}
        else:
            if (not tp1_hit) and (low <= tp1):
                tp1_hit = True
                sl = entry
            if high >= sl:
                result = "BE" if tp1_hit else "LOSS"
                return {"result": result, "exit": sl, "bars": i - start_i}
            if low <= tp3:
                return {"result": "WIN", "exit": tp3, "bars": i - start_i}

    return {"result": "OPEN", "exit": None, "bars": len(df) - start_i}

def _get_scenarios(sub: pd.DataFrame, macro_trend: str, rsi14: float, is_vol_spike: bool) -> List[Dict]:
    pivots = find_fractal_pivots(sub)
    pivots = filter_pivots(pivots, min_pct_move=1.5)
    if len(pivots) < 4:
        return []

    scenarios = build_scenarios(
        pivots,
        macro_trend=macro_trend,
        rsi14=rsi14,
        volume_spike=is_vol_spike,
    )
    if not scenarios:
        return []

    regime = detect_market_regime(sub)
    macro_bias = compute_macro_bias(regime, rsi14=rsi14)

    gated: List[Dict] = []
    for sc in scenarios:
        r = apply_context_gate(sc, macro_bias=macro_bias, min_confidence=MIN_CONFIDENCE_LIVE)
        if r:
            gated.append(r)

    return gated

def _r_multiple(direction: str, entry: float, sl: float, tp3: float, result: str) -> float:
    risk = abs(entry - sl)
    if risk <= 0:
        return 0.0
    rr_tp3 = abs(tp3 - entry) / risk
    if result == "LOSS":
        return -1.0
    if result == "WIN":
        return float(rr_tp3)
    if result == "BE":
        return 0.0
    return 0.0

def _bucket_stats(trades: List[Dict], min_conf: float) -> Dict:
    bucket = [t for t in trades if float(t.get("confidence") or 0) >= min_conf]
    w = sum(1 for t in bucket if t["result"] == "WIN")
    l = sum(1 for t in bucket if t["result"] == "LOSS")
    o = sum(1 for t in bucket if t["result"] == "OPEN")
    closed = w + l
    wr = round((w / closed) * 100, 2) if closed > 0 else 0.0
    return {"trades": len(bucket), "wins": w, "losses": l, "open": o, "winrate": wr}

def _safe_entry_time(t: Dict):
    v = t.get("entry_time")
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return pd.Timestamp.min.tz_localize("UTC")
    if isinstance(v, pd.Timestamp) and pd.isna(v):
        return pd.Timestamp.min.tz_localize("UTC")
    return v

def _mirror_live_filters(sub: pd.DataFrame, symbol: str, direction: str) -> bool:
    """
    คืน True = ผ่าน filter, False = ควร skip
    รวม weekly_permit + trend_ok ไว้ที่เดียว ใช้ใน backtest_symbol และ backtest_symbol_trades
    """
    # weekly_permit (HARD block เหมือน live)
    mtf = get_mtf_summary(symbol) or {}
    weekly_permit_long = bool(mtf.get("weekly_permit_long", True))
    weekly_permit_short = bool(mtf.get("weekly_permit_short", True))

    if direction == "LONG" and not weekly_permit_long:
        return False
    if direction == "SHORT" and not weekly_permit_short:
        return False

    # trend_ok (HARD block เหมือน live)
    ema50 = float(sub["ema50"].iloc[-1])
    ema200 = float(sub["ema200"].iloc[-1])
    ema200_prev = float(sub["ema200"].iloc[-2]) if len(sub) >= 2 else ema200
    trend_ok_long  = (ema50 > ema200) and (ema200 > ema200_prev)
    trend_ok_short = (ema50 < ema200) and (ema200 < ema200_prev)

    if direction == "LONG" and not trend_ok_long:
        return False
    if direction == "SHORT" and not trend_ok_short:
        return False

    return True

# ---------------------------------------------------------------------------
# backtest_symbol
# ---------------------------------------------------------------------------

def backtest_symbol(
    symbol: str,
    interval: str = "1d",
    limit: int = 1000,
    min_pct_move: float = 1.5,
    min_rr: float = 0.0,
) -> Dict:
    invalid_reasons = Counter()

    _empty = {
        "symbol": symbol,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "open": 0,
        "winrate": 0.0,
        "conf_min": 0.0,
        "conf_max": 0.0,
        "conf_avg": 0.0,
        "buckets": _EMPTY_BUCKETS,
    }

    df = _prepare_df(symbol, interval, limit)
    if df is None:
        return _empty

    trades: List[Dict] = []
    in_position = False
    skip_until_bar = 0

    if not min_rr or float(min_rr) <= 0:
        try:
            from app.config.wave_settings import MIN_RR as _LIVE_MIN_RR
            min_rr = float(_LIVE_MIN_RR) if _LIVE_MIN_RR else 2.0
        except Exception:
            min_rr = 2.0

    for i in range(_START_BAR, len(df) - 1):
        if in_position or i < skip_until_bar:
            continue

        sub = df.iloc[: i + 1].copy()
        macro_trend = trend_filter_ema(sub)
        rsi14 = float(sub["rsi14"].iloc[-1])
        is_vol_spike = bool(volume_spike(sub, length=20, multiplier=1.5))
        last_close = float(sub["close"].iloc[-1])

        atr = float(sub["atr14"].iloc[-1])
        atr_ma50 = float(sub["atr14"].rolling(50).mean().iloc[-1]) if len(sub) >= 50 else 0.0
        if atr_ma50 > 0 and atr >= atr_ma50:
            continue

        scenarios = _get_scenarios(sub, macro_trend, rsi14, is_vol_spike)
        if not scenarios:
            continue

        sc = scenarios[0]
        direction = sc["direction"]

        # --- Mirror live filters ---
        if not _mirror_live_filters(sub, symbol, direction):
            continue

        trade_plan = build_trade_plan(sc, current_price=last_close, min_rr=min_rr)
        if not trade_plan.get("valid"):
            invalid_reasons[str(trade_plan.get("reason") or "NO_REASON")] += 1
            continue

        entry = float(trade_plan["entry"])

        stype = (sc.get("type") or "").upper()
        if stype in ("ABC_UP", "ABC_DOWN"):
            triggered = True
        else:
            triggered = (
                (direction == "LONG" and last_close > entry)
                or (direction == "SHORT" and last_close < entry)
            )
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
            "trade_plan": trade_plan,
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

        logger.debug("bar=%d dir=%s conf=%.1f result=%s", i, direction, trades[-1]["confidence"], sim["result"])

        if sim["result"] in ("WIN", "LOSS", "BE"):
            in_position = False
        else:
            skip_until_bar = (i + 1) + int(sim["bars"])

    INVALID_REASONS.update(invalid_reasons)

    wins = sum(1 for t in trades if t["result"] == "WIN")
    losses = sum(1 for t in trades if t["result"] == "LOSS")
    bes = sum(1 for t in trades if t["result"] == "BE")
    opens = sum(1 for t in trades if t["result"] == "OPEN")
    total_closed = wins + losses + bes
    winrate = round((wins / total_closed) * 100, 2) if total_closed > 0 else 0.0

    conf_values = [float(t.get("confidence") or 0) for t in trades]
    conf_min = round(min(conf_values), 2) if conf_values else 0.0
    conf_max = round(max(conf_values), 2) if conf_values else 0.0
    conf_avg = round(sum(conf_values) / len(conf_values), 2) if conf_values else 0.0

    return {
        "symbol": symbol,
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "be": bes,
        "open": opens,
        "winrate": winrate,
        "conf_min": conf_min,
        "conf_max": conf_max,
        "conf_avg": conf_avg,
        "buckets": {
            "conf>=60": _bucket_stats(trades, 60),
            "conf>=70": _bucket_stats(trades, 70),
            "conf>=80": _bucket_stats(trades, 80),
        },
        "invalid_reasons": invalid_reasons,
    }


# ---------------------------------------------------------------------------
# backtest_symbol_trades
# ---------------------------------------------------------------------------

def backtest_symbol_trades(
    symbol: str,
    interval: str = "1d",
    limit: int = 1000,
    min_pct_move: float = 1.5,
    min_rr: float = 0.0,
    min_confidence: float = 0.0,
) -> Dict:
    df = _prepare_df(symbol, interval, limit)
    if df is None:
        return {"symbol": symbol, "trades": []}

    trades: List[Dict] = []
    in_position = False
    skip_until_bar = 0

    if not min_rr or float(min_rr) <= 0:
        try:
            from app.config.wave_settings import MIN_RR as _LIVE_MIN_RR
            min_rr = float(_LIVE_MIN_RR) if _LIVE_MIN_RR else 2.0
        except Exception:
            min_rr = 2.0

    for i in range(_START_BAR, len(df) - 1):
        if in_position or i < skip_until_bar:
            continue

        sub = df.iloc[: i + 1].copy()
        macro_trend = trend_filter_ema(sub)
        rsi14 = float(sub["rsi14"].iloc[-1])
        is_vol_spike = bool(volume_spike(sub, length=20, multiplier=1.5))
        last_close = float(sub["close"].iloc[-1])

        atr = float(sub["atr14"].iloc[-1])
        atr_ma50 = float(sub["atr14"].rolling(50).mean().iloc[-1]) if len(sub) >= 50 else 0.0
        if atr_ma50 > 0 and atr >= atr_ma50:
            continue

        scenarios = _get_scenarios(sub, macro_trend, rsi14, is_vol_spike)
        if not scenarios:
            continue

        sc = scenarios[0]
        direction = sc["direction"]

        # --- Mirror live filters ---
        if not _mirror_live_filters(sub, symbol, direction):
            continue

        conf = float(sc.get("confidence") or sc.get("score") or 0)
        if conf < float(min_confidence):
            continue

        trade_plan = build_trade_plan(sc, current_price=last_close, min_rr=min_rr)
        if not trade_plan.get("valid"):
            continue

        entry = float(trade_plan["entry"])

        stype = (sc.get("type") or "").upper()
        if stype in ("ABC_UP", "ABC_DOWN"):
            triggered = True
        else:
            triggered = (
                (direction == "LONG" and last_close > entry)
                or (direction == "SHORT" and last_close < entry)
            )
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

        exit_index: Optional[int] = None
        exit_time = None
        if sim["result"] in ("WIN", "LOSS", "BE"):
            exit_index = start_i + int(sim["bars"])
            if 0 <= exit_index < len(df):
                exit_time = df["open_time"].iloc[exit_index]

        entry_time = df["open_time"].iloc[i]
        r = _r_multiple(direction, entry, float(trade_plan["sl"]), float(trade_plan["tp3"]), sim["result"])

        if sim["result"] in ("WIN", "LOSS", "BE"):
            try:
                sqlite3 = __import__("sqlite3")
                json = __import__("json")

                def _ts_to_int(ts):
                    if ts is None:
                        return None
                    try:
                        return int(ts.timestamp())
                    except Exception:
                        return None

                meta = {
                    "scenario_type": sc.get("type"),
                    "macro_trend": macro_trend,
                    "rsi14": rsi14,
                    "vol_spike": is_vol_spike,
                    "confidence": conf,
                    "trade_plan": trade_plan,
                }

                con = sqlite3.connect("data/market.db")
                cur = con.cursor()
                cur.execute(
                    """
                    INSERT INTO trades (
                        symbol, timeframe, entry_ts, exit_ts, direction,
                        entry, sl, tp1, tp2, tp3,
                        result, r_multiple, meta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol, interval,
                        _ts_to_int(entry_time), _ts_to_int(exit_time),
                        direction,
                        float(entry), float(trade_plan["sl"]),
                        float(trade_plan["tp1"]), float(trade_plan["tp2"]), float(trade_plan["tp3"]),
                        str(sim["result"]), float(r),
                        json.dumps(meta, ensure_ascii=False),
                    ),
                )
                con.commit()
                con.close()

            except Exception as e:
                logger.warning(f"[{symbol}] sqlite insert trade failed: {e}")

        trades.append({
            "trade_plan": trade_plan,
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

        if sim["result"] in ("WIN", "LOSS", "BE"):
            in_position = False
        else:
            skip_until_bar = (i + 1) + int(sim["bars"])

    return {"symbol": symbol, "trades": trades, "data": df}


# ---------------------------------------------------------------------------
# portfolio_simulator
# ---------------------------------------------------------------------------

def portfolio_simulator(
    symbols: List[str],
    interval: str = "1d",
    limit: int = 1000,
    min_pct_move: float = 1.5,
    min_rr: float = 2.0,
    min_confidence: float = 60.0,
    return_trades_detail: bool = False,
) -> Dict:
    all_trades: List[Dict] = []

    try:
        import sqlite3
        con = sqlite3.connect("data/market.db")
        cur = con.cursor()
        cur.execute("DELETE FROM trades")
        con.commit()
        con.close()
    except Exception as e:
        logger.warning(f"sqlite reset trades failed: {e}")

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

    all_trades.sort(key=_safe_entry_time)

    closed = [t for t in all_trades if t["result"] in ("WIN", "LOSS", "BE")]
    wins = sum(1 for t in closed if t["result"] == "WIN")
    losses = sum(1 for t in closed if t["result"] == "LOSS")
    bes = sum(1 for t in closed if t["result"] == "BE")
    total = len(closed)
    winrate = round((wins / total) * 100, 2) if total > 0 else 0.0

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    curve: List[float] = []

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
        "be": bes,
        "equity_R": round(equity, 2),
        "max_drawdown_R": round(max_dd, 2),
        "trades_detail": closed if return_trades_detail else None,
    }


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from app.config.wave_settings import SYMBOLS
    symbols = SYMBOLS

    res = portfolio_simulator(symbols, interval="4h", limit=1000, min_confidence=MIN_CONFIDENCE_LIVE)
    print(res)
