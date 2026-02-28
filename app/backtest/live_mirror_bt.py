from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.config.wave_settings import BARS, TIMEFRAME
from app.data.binance_fetcher import fetch_ohlcv, drop_unclosed_candle
from app.indicators.atr import add_atr
from app.indicators.ema import add_ema

@dataclass
class Trade:
    symbol: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    opened_at: pd.Timestamp
    closed_at: pd.Timestamp
    exit_price: float
    result: str  # "WIN" | "WIN_P1" | "WIN_P2" | "LOSS" | "FLAT"
    r_multiple: float

def _r_multiple(direction: str, entry: float, sl: float, exit_price: float, result: str = "") -> float:
    risk = abs(entry - sl)
    if risk <= 0:
        return 0.0

    # partial win: 30/30/40
    if result == "WIN_P1": return round(0.3 * 1.0, 3)                      # +0.3R
    if result == "WIN_P2": return round(0.3 * 1.0 + 0.3 * 1.618, 3)       # +0.785R

    if direction.upper() == "LONG":
        return (exit_price - entry) / risk
    return (entry - exit_price) / risk

def _simulate_trade_on_forward_bars(
    df: pd.DataFrame,
    i_open: int,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    tp1: float = 0.0,
    tp2: float = 0.0,
) -> Tuple[int, float, str]:
    """
    Mirror live trade_executor.py:
    - วาง STOP_MARKET (SL) + TAKE_PROFIT_MARKET (TP3) เท่านั้น
    - TP1 hit → ย้าย SL ไป BE → ถ้าโดน SL = WIN_P1
    - TP2 hit → ถ้าโดน SL = WIN_P2
    - SL ชนก่อนเสมอในแท่งเดียวกัน (conservative)
    """
    direction = direction.upper()
    tp1_hit = False
    tp2_hit = False

    for j in range(i_open, len(df)):
        hi = float(df["high"].iloc[j])
        lo = float(df["low"].iloc[j])

        if direction == "LONG":
            if tp1 > 0 and (not tp1_hit) and hi >= tp1:
                tp1_hit = True
                sl = entry  # ย้าย BE
            if tp2 > 0 and tp1_hit and (not tp2_hit) and hi >= tp2:
                tp2_hit = True

            if lo <= sl:
                if tp2_hit:   return j, sl, "WIN_P2"
                elif tp1_hit: return j, sl, "WIN_P1"
                else:         return j, sl, "LOSS"
            if hi >= tp:
                return j, tp, "WIN"
        else:
            if tp1 > 0 and (not tp1_hit) and lo <= tp1:
                tp1_hit = True
                sl = entry
            if tp2 > 0 and tp1_hit and (not tp2_hit) and lo <= tp2:
                tp2_hit = True

            if hi >= sl:
                if tp2_hit:   return j, sl, "WIN_P2"
                elif tp1_hit: return j, sl, "WIN_P1"
                else:         return j, sl, "LOSS"
            if lo <= tp:
                return j, tp, "WIN"

    return len(df) - 1, float(df["close"].iloc[-1]), "FLAT"

def _streaks(results: List[str]) -> Dict[str, int]:
    best_win = best_loss = 0
    cur_win = cur_loss = 0

    for r in results:
        if r in ("WIN", "WIN_P1", "WIN_P2"):
            cur_win += 1
            cur_loss = 0
        elif r == "LOSS":
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = 0
            cur_loss = 0

        best_win = max(best_win, cur_win)
        best_loss = max(best_loss, cur_loss)

    return {"max_win_streak": best_win, "max_loss_streak": best_loss}

def _equity_and_dd_r(trades: List[Trade]) -> Dict[str, float]:
    eq = 0.0
    peak = 0.0
    max_dd = 0.0

    for t in trades:
        eq += float(t.r_multiple)
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    return {"equity_R": round(eq, 4), "max_dd_R": round(max_dd, 4)}

def _coerce_ohlcv_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    need = {"open_time", "open", "high", "low", "close", "volume"}
    missing = [c for c in sorted(need) if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    s = df["open_time"]
    s_num = pd.to_numeric(s, errors="coerce")
    if s_num.notna().all():
        dt = pd.to_datetime(s_num.astype("int64"), unit="ms", utc=True)
    else:
        dt = pd.to_datetime(s, utc=True, errors="raise")

    df["open_time"] = dt

    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["open_time", "open", "high", "low", "close"]).copy()
    df = df.set_index("open_time", drop=False).sort_index()

    return df

def _load_df_from_csv(csv_path: str) -> Optional[pd.DataFrame]:
    """
    โหลดจาก CSV โดยไม่ cap limit
    เพราะ CSV มีข้อมูลเท่าไหร่ ต้องใช้ทั้งหมด
    เพื่อให้ MTF slice ณ bar i ได้ถูกต้อง
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    df = _coerce_ohlcv_types(df)
    return drop_unclosed_candle(df)

def _load_df_from_api(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    df = fetch_ohlcv(symbol, interval=interval, limit=limit)
    return drop_unclosed_candle(df)

def _patch_live_for_offline(
    sub_df: pd.DataFrame,
    df_4h: Optional[pd.DataFrame],
    df_1w: Optional[pd.DataFrame],
) -> None:
    """
    Patch ทุก namespace ที่เรียก fetch_ohlcv ให้ใช้ข้อมูล historical ณ bar i

    slice MTF ด้วย timestamp ป้องกัน lookahead bias
    """
    import app.analysis.wave_engine as we_mod
    import app.analysis.multi_tf as mtf_mod
    import app.data.binance_fetcher as bf_mod

    current_ts = sub_df.index[-1]

    def _patched_fetch(symbol, interval=TIMEFRAME, limit=BARS):
        if interval == TIMEFRAME:
            return sub_df.copy()

        if interval == "4h":
            if df_4h is not None and len(df_4h) > 0:
                sliced = df_4h[df_4h.index <= current_ts].tail(int(limit)).copy()
                return sliced if len(sliced) > 0 else pd.DataFrame()
            return pd.DataFrame()

        if interval == "1w":
            if df_1w is not None and len(df_1w) > 0:
                sliced = df_1w[df_1w.index <= current_ts].tail(int(limit)).copy()
                return sliced if len(sliced) > 0 else pd.DataFrame()
            return pd.DataFrame()

        return pd.DataFrame()

    we_mod.fetch_ohlcv = _patched_fetch
    mtf_mod.fetch_ohlcv = _patched_fetch
    bf_mod.fetch_ohlcv = _patched_fetch

def run_symbol_bt(
    symbol: str,
    limit: int = BARS,
    csv_path: Optional[str] = None,
    csv_path_4h: Optional[str] = None,
    csv_path_1w: Optional[str] = None,
) -> Dict:

    # โหลด 1D
    if csv_path:
        df = _load_df_from_csv(csv_path)
        if df is not None and limit and len(df) > limit:
            df = df.tail(limit).copy()
    else:
        df = _load_df_from_api(symbol, TIMEFRAME, limit)

    if df is None or len(df) < 300:
        return {"symbol": symbol, "trades": [], "summary": {"n": 0}}

    # ✅ เพิ่ม indicator เพื่อให้ ATR Gate ทำงานได้
    df = add_atr(df, length=14)
    df = add_ema(df, lengths=(50, 200))

    # โหลด 4H — โหลดทั้งหมดจาก CSV ไม่ cap
    df_4h: Optional[pd.DataFrame] = None
    if csv_path_4h:
        df_4h = _load_df_from_csv(csv_path_4h)
        print(f"[MTF] 4H loaded: {len(df_4h) if df_4h is not None else 0} bars")
    else:
        print("[MTF] WARNING: --csv4h ไม่ได้ระบุ → h4_confirm=False ตลอด")

    # โหลด 1W — โหลดทั้งหมดจาก CSV ไม่ cap
    df_1w: Optional[pd.DataFrame] = None
    if csv_path_1w:
        df_1w = _load_df_from_csv(csv_path_1w)
        print(f"[MTF] 1W loaded: {len(df_1w) if df_1w is not None else 0} bars")
    else:
        print("[MTF] WARNING: --csv1w ไม่ได้ระบุ → weekly_permit=True/True ตลอด")

    from app.analysis.wave_engine import analyze_symbol as live_analyze_symbol

    trades: List[Trade] = []

    # --- debug counters (enable with env BT_DEBUG=1) ---
    bt_debug = (os.getenv("BT_DEBUG", "") or "").lower() in ("1", "true", "yes")
    dbg = {
        "bars": 0,
        "out_none": 0,
        "no_scenarios": 0,
        "sc_total": 0,
        "sc_ready": 0,
        "plan_allowed": 0,
        "plan_triggered": 0,
        "plan_valid": 0,
        "trades": 0,
    }

    in_trade = False
    skip_until = 0
    window_len = int(limit) if limit else BARS

    for i in range(250, len(df) - 2):
        dbg["bars"] += 1

        if in_trade or i < skip_until:
            continue

        start = max(0, (i + 1) - window_len)
        sub = df.iloc[start : i + 1].copy()

        _patch_live_for_offline(sub, df_4h, df_1w)

        out = live_analyze_symbol(symbol)
        if not out:
            dbg["out_none"] += 1
            continue

        scenarios_list = (out.get("scenarios") or [])
        if not scenarios_list:
            dbg["no_scenarios"] += 1
            continue

        triggered_this_bar = False

        for sc in scenarios_list:
            if triggered_this_bar:
                break

            plan = (sc.get("trade_plan") or {})
            dbg["sc_total"] += 1

            if (sc.get("status") or "").upper() != "READY":
                continue
            dbg["sc_ready"] += 1

            if not plan.get("allowed_to_trade"):
                continue
            dbg["plan_allowed"] += 1

            # NOTE: อย่าเชื่อ plan.triggered จาก live แบบ 1D close-only
            # เพราะ live ใช้ "ราคาปัจจุบัน" ที่สามารถแตะ entry intrabar ได้
            # ใน backtest เราจำลอง trigger ด้วยแท่งถัดไป (i+1) แบบ conservative:
            # - LONG: ถ้า high ของแท่งถัดไป >= entry → ถือว่า triggered
            # - SHORT: ถ้า low  ของแท่งถัดไป <= entry → ถือว่า triggered
            entry = plan.get("entry")
            if entry is None:
                continue
            entry_f = float(entry)

            next_hi = float(df["high"].iloc[i + 1])
            next_lo = float(df["low"].iloc[i + 1])

            direction_tmp = (sc.get("direction") or "").upper()
            is_triggered = False
            if direction_tmp == "LONG":
                is_triggered = next_hi >= entry_f
            elif direction_tmp == "SHORT":
                is_triggered = next_lo <= entry_f

            if not is_triggered:
                continue
            dbg["plan_triggered"] += 1

            if not plan.get("valid"):
                continue
            dbg["plan_valid"] += 1

            direction = (sc.get("direction") or "").upper()
            if direction not in ("LONG", "SHORT"):
                continue

            sl  = plan.get("stop_loss")     or plan.get("sl")
            tp3 = plan.get("take_profit_3") or plan.get("tp3")
            tp1 = plan.get("take_profit_1") or plan.get("tp1")
            tp2 = plan.get("take_profit_2") or plan.get("tp2")

            if sl is None or tp3 is None:
                continue

            # ใช้ entry ตามแผน (mirror live) ไม่ใช่ open ของแท่งถัดไป
            entry_px = float(entry_f)
            sl_f     = float(sl)
            tp3_f    = float(tp3)

            j_close, exit_px, res = _simulate_trade_on_forward_bars(
                df=df,
                i_open=i + 1,
                direction=direction,
                entry=entry_px,
                sl=sl_f,
                tp=tp3_f,
                tp1=float(tp1) if tp1 is not None else 0.0,
                tp2=float(tp2) if tp2 is not None else 0.0,
            )

            r = _r_multiple(direction, entry_px, sl_f, float(exit_px), result=res)

            trades.append(
                Trade(
                    symbol=symbol,
                    direction=direction,
                    entry=entry_px,
                    sl=sl_f,
                    tp1=float(tp1) if tp1 is not None else float("nan"),
                    tp2=float(tp2) if tp2 is not None else float("nan"),
                    tp3=tp3_f,
                    opened_at=pd.to_datetime(df.index[i + 1]),
                    closed_at=pd.to_datetime(df.index[j_close]),
                    exit_price=float(exit_px),
                    result=res,
                    r_multiple=float(r),
                )
            )
            dbg["trades"] += 1

            triggered_this_bar = True
            # cool-down 5 bar หลัง loss กันเข้าซ้ำ pivot เดิม
            cooldown = 5 if res == "LOSS" else 0
            skip_until = j_close + 1 + cooldown

    if not trades:
        if bt_debug:
            print(f"[BT_DEBUG] {symbol} debug: {dbg}")
        return {"symbol": symbol, "trades": [], "summary": {"n": 0}}

    results = [t.result for t in trades]
    wins   = sum(1 for r in results if r in ("WIN", "WIN_P1", "WIN_P2"))
    losses = sum(1 for r in results if r == "LOSS")
    flats  = sum(1 for r in results if r == "FLAT")
    win_p1 = sum(1 for r in results if r == "WIN_P1")
    win_p2 = sum(1 for r in results if r == "WIN_P2")
    win_full = sum(1 for r in results if r == "WIN")

    total_r = sum(float(t.r_multiple) for t in trades)
    streak  = _streaks(results)
    eqdd    = _equity_and_dd_r(trades)

    summary = {
        "n": len(trades),
        "wins": wins,
        "wins_full": win_full,
        "wins_p2": win_p2,
        "wins_p1": win_p1,
        "losses": losses,
        "flats": flats,
        "winrate": round((wins / len(trades) * 100.0), 2) if trades else 0.0,
        "total_R": round(total_r, 4),
        **eqdd,
        **streak,
    }

    if bt_debug:
        print(f"[BT_DEBUG] {symbol} debug: {dbg}")

    return {
        "symbol": symbol,
        "trades": [t.__dict__ for t in trades],
        "summary": summary,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--limit",  type=int, default=BARS)
    ap.add_argument("--csv",    default="", help="path to 1D OHLCV csv")
    ap.add_argument("--csv4h",  default="", help="path to 4H OHLCV csv")
    ap.add_argument("--csv1w",  default="", help="path to 1W OHLCV csv")
    ap.add_argument("--out",    default="", help="path to write trades csv")
    args = ap.parse_args()

    out = run_symbol_bt(
        args.symbol,
        limit=int(args.limit),
        csv_path=args.csv.strip()   or None,
        csv_path_4h=args.csv4h.strip() or None,
        csv_path_1w=args.csv1w.strip() or None,
    )

    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))

    # เขียนไฟล์เสมอถ้าระบุ --out (แม้ไม่มีเทรด) เพื่อให้ตรวจ/อ่านไฟล์ได้
    if args.out.strip():
        # ถ้าไม่มีเทรด ให้เขียนเป็น CSV ว่างแต่มี header เพื่ออ่านด้วย pandas ได้เสมอ
        cols = [
            "symbol",
            "direction",
            "entry",
            "sl",
            "tp1",
            "tp2",
            "tp3",
            "opened_at",
            "closed_at",
            "exit_price",
            "result",
            "r_multiple",
        ]
        rows = out.get("trades") or []
        tdf = pd.DataFrame(rows)
        if tdf.empty:
            tdf = pd.DataFrame(columns=cols)
        else:
            # กันคอลัมน์หาย/สลับลำดับ
            for c in cols:
                if c not in tdf.columns:
                    tdf[c] = pd.NA
            tdf = tdf[cols]

        tdf.to_csv(args.out.strip(), index=False)
        print(f"OK: wrote trades -> {args.out.strip()}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())