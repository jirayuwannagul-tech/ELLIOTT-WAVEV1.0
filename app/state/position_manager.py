import os
import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# ✅ ใช้ DB เดียวกับ performance (กำหนดผ่าน ENV ได้)
DB_PATH = Path(os.getenv("ELLIOTT_DB", "/var/lib/elliott/positions.db"))


def _get_conn() -> sqlite3.Connection:
    # ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.commit()


# เรียก init ตอน import
_init_db()


@dataclass
class Position:
    symbol: str
    timeframe: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    qty: float
    status: str
    remaining_qty: float = 0.0
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    opened_at: str = ""
    closed_at: str = ""
    closed_reason: str = ""


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _key(symbol: str, timeframe: str) -> str:
    return f"{symbol}:{timeframe}".upper()


def _load_position(key: str) -> Optional[Dict]:
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT data FROM positions WHERE key = ?", (key,)
            ).fetchone()
            if row:
                return json.loads(row["data"])
            return None
    except Exception as e:
        logger.error(f"_load_position {key} error: {e}")
        return None


def _save_position(key: str, data: Dict) -> None:
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO positions (key, data) VALUES (?, ?)",
                (key, json.dumps(data, ensure_ascii=False))
            )
            conn.commit()
    except Exception as e:
        logger.error(f"_save_position {key} error: {e}")


def get_active(symbol: str, timeframe: str) -> Optional[Position]:
    try:
        k = _key(symbol, timeframe)
        raw = _load_position(k)
        if not raw:
            return None
        pos = Position(**raw)
        if pos.status == "ACTIVE":
            return pos
        return None
    except Exception as e:
        logger.error(f"get_active {symbol} error: {e}")
        return None


def list_active_positions(timeframe: str) -> List[Position]:
    """ดึง ACTIVE ทั้งหมดจาก DB (กรองด้วย timeframe)"""
    out: List[Position] = []
    try:
        with _get_conn() as conn:
            rows = conn.execute("SELECT data FROM positions").fetchall()
        for r in rows:
            raw = json.loads(r["data"])
            if (raw.get("status") == "ACTIVE") and (str(raw.get("timeframe")).upper() == str(timeframe).upper()):
                out.append(Position(**raw))
        return out
    except Exception as e:
        logger.error(f"list_active_positions error: {e}")
        return []


def lock_new_position(
    symbol: str, timeframe: str, direction: str, trade_plan: Dict
) -> bool:
    try:
        k = _key(symbol, timeframe)
        raw = _load_position(k)
        if raw and raw.get("status") == "ACTIVE":
            return False

        qty = float(trade_plan.get("qty") or 0.0)

        pos = Position(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry=float(trade_plan["entry"]),
            sl=float(trade_plan["sl"]),
            tp1=float(trade_plan["tp1"]),
            tp2=float(trade_plan["tp2"]),
            tp3=float(trade_plan["tp3"]),
            qty=qty,
            remaining_qty=qty,
            status="ACTIVE",
            opened_at=_now_iso(),
        )

        _save_position(k, asdict(pos))
        return True
    except Exception as e:
        logger.error(f"lock_new_position {symbol} error: {e}")
        return False


def update_from_price(
    symbol: str, timeframe: str, price: float
) -> Tuple[Optional[Position], Dict]:
    try:
        k = _key(symbol, timeframe)
        raw = _load_position(k)
        if not raw:
            return None, {}

        pos = Position(**raw)
        if pos.status != "ACTIVE":
            return pos, {}

        p = float(price)
        events = {
            "tp1": False, "tp2": False, "tp3": False,
            "sl": False, "closed": False, "closed_reason": ""
        }

        if pos.direction == "LONG":
            if (not pos.tp1_hit) and p >= pos.tp1:
                pos.tp1_hit = True
                events["tp1"] = True
            if (not pos.tp2_hit) and p >= pos.tp2:
                pos.tp2_hit = True
                events["tp2"] = True
            if (not pos.tp3_hit) and p >= pos.tp3:
                pos.tp3_hit = True
                events["tp3"] = True
            if (not pos.sl_hit) and p <= pos.sl:
                pos.sl_hit = True
                events["sl"] = True
        else:
            if (not pos.tp1_hit) and p <= pos.tp1:
                pos.tp1_hit = True
                events["tp1"] = True
            if (not pos.tp2_hit) and p <= pos.tp2:
                pos.tp2_hit = True
                events["tp2"] = True
            if (not pos.tp3_hit) and p <= pos.tp3:
                pos.tp3_hit = True
                events["tp3"] = True
            if (not pos.sl_hit) and p >= pos.sl:
                pos.sl_hit = True
                events["sl"] = True

        if pos.sl_hit and pos.status == "ACTIVE":
            pos.status = "CLOSED"
            pos.closed_at = _now_iso()
            pos.closed_reason = "SL"
            events["closed"] = True
            events["closed_reason"] = "SL"
        elif pos.tp3_hit and pos.status == "ACTIVE":
            pos.status = "CLOSED"
            pos.closed_at = _now_iso()
            pos.closed_reason = "TP3"
            events["closed"] = True
            events["closed_reason"] = "TP3"

        _save_position(k, asdict(pos))
        return pos, events

    except Exception as e:
        logger.error(f"update_from_price {symbol} error: {e}")
        return None, {}