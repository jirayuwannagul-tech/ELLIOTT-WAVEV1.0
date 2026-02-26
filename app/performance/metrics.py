# app/performance/metrics.py
from __future__ import annotations

import os
import json
import math
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(os.getenv("ELLIOTT_DB", "/var/lib/elliott/positions.db"))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_all_positions() -> List[Dict]:
    if not DB_PATH.exists():
        return []
    try:
        with _get_conn() as conn:
            rows = conn.execute("SELECT data FROM positions").fetchall()
        return [json.loads(r["data"]) for r in rows]
    except Exception:
        return []


def compute_metrics(positions: Optional[List[Dict]] = None) -> Dict:
    if positions is None:
        positions = load_all_positions()

    closed = [p for p in positions if p.get("status") == "CLOSED"]
    active = [p for p in positions if p.get("status") == "ACTIVE"]

    # R-multiple per trade (Partial Exit 30/30/40, TP3=4R)
    r_multiples: List[float] = []

    for p in closed:
        entry = float(p.get("entry", 0) or 0)
        sl = float(p.get("sl", 0) or 0)

        risk = abs(entry - sl)
        if risk <= 0:
            continue

        # weights
        w1, w2, w3 = 0.3, 0.3, 0.4

        r = 0.0

        # TP1
        if p.get("tp1_hit"):
            r += w1 * 1.0

        # TP2
        if p.get("tp2_hit"):
            r += w2 * 2.0

        # TP3
        if p.get("tp3_hit"):
            r += w3 * 4.0

        # Remaining position hits SL
        if p.get("sl_hit"):
            remaining = 1.0
            if p.get("tp1_hit"):
                remaining -= w1
            if p.get("tp2_hit"):
                remaining -= w2
            if p.get("tp3_hit"):
                remaining -= w3

            r += remaining * (-1.0)

        r_multiples.append(round(r, 3))

    total_closed = len(closed)
    total_scored = len(r_multiples)

    wins = [r for r in r_multiples if r > 0]
    losses = [r for r in r_multiples if r < 0]

    win_count = len(wins)
    loss_count = len(losses)
    winrate = round((win_count / total_scored) * 100, 2) if total_scored > 0 else 0.0

    # Equity curve
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    equity_curve: List[float] = []
    for r in r_multiples:
        equity += r
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        equity_curve.append(round(equity, 3))

    total_r = round(equity, 3)

    # Sharpe Ratio (annualized, assume 1 trade/day avg)
    sharpe = 0.0
    if len(r_multiples) >= 2:
        mean_r = sum(r_multiples) / len(r_multiples)
        variance = sum((r - mean_r) ** 2 for r in r_multiples) / len(r_multiples)
        std_r = math.sqrt(variance)
        if std_r > 0:
            sharpe = round((mean_r / std_r) * math.sqrt(252), 2)

    # Profit factor
    gross_profit = sum(r for r in r_multiples if r > 0)
    gross_loss = abs(sum(r for r in r_multiples if r < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0

    # Avg R (ชื่อเดิม avg_rr)
    avg_rr = round(sum(r_multiples) / len(r_multiples), 2) if r_multiples else 0.0

    # Per symbol breakdown
    symbol_stats: Dict[str, Dict] = {}
    for p in closed:
        sym = p.get("symbol", "?")
        if sym not in symbol_stats:
            symbol_stats[sym] = {"wins": 0, "losses": 0}
        if p.get("closed_reason") == "TP3":
            symbol_stats[sym]["wins"] += 1
        elif p.get("closed_reason") == "SL":
            symbol_stats[sym]["losses"] += 1

    for sym, s in symbol_stats.items():
        t = s["wins"] + s["losses"]
        s["winrate"] = round((s["wins"] / t) * 100, 1) if t > 0 else 0.0
        s["total"] = t

    return {
        "total_closed": total_closed,
        "total_scored": total_scored,
        "active": len(active),
        "win_count": win_count,
        "loss_count": loss_count,
        "winrate": winrate,
        "total_r": total_r,
        "max_drawdown_r": round(max_dd, 3),
        "sharpe_ratio": sharpe,
        "profit_factor": profit_factor,
        "avg_rr": avg_rr,
        "equity_curve": equity_curve,
        "symbol_stats": symbol_stats,
        "closed_positions": closed,
        "active_positions": active,
    }