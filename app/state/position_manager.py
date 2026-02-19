import json
import logging
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

STATE_PATH = Path("positions.json")
BACKUP_PATH = Path("positions.backup.json")


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
    status: str
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    opened_at: str = ""
    closed_at: str = ""
    closed_reason: str = ""


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_state() -> Dict:
    # ถ้าไม่มีไฟล์ → คืนค่าว่าง
    if not STATE_PATH.exists():
        return {"positions": {}}

    # พยายามอ่านไฟล์หลัก
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data or {"positions": {}}
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"positions.json เสียหาย: {e} — พยายามใช้ backup")

    # ถ้าไฟล์หลักพัง → ลอง backup
    if BACKUP_PATH.exists():
        try:
            with BACKUP_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                logger.warning("ใช้ positions.backup.json แทน")
                return data or {"positions": {}}
        except Exception as e2:
            logger.error(f"backup ก็เสียหาย: {e2} — เริ่มใหม่จากว่าง")

    # ถ้าทั้งคู่พัง → เริ่มใหม่
    return {"positions": {}}


def _save_state(state: Dict) -> None:
    # backup ก่อนเขียนทับ
    try:
        if STATE_PATH.exists():
            shutil.copy2(STATE_PATH, BACKUP_PATH)
    except Exception as e:
        logger.warning(f"backup ล้มเหลว: {e}")

    # เขียนไฟล์ใหม่
    try:
        with STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"บันทึก positions.json ล้มเหลว: {e}")


def _key(symbol: str, timeframe: str) -> str:
    return f"{symbol}:{timeframe}".upper()


def get_active(symbol: str, timeframe: str) -> Optional[Position]:
    try:
        state = _load_state()
        k = _key(symbol, timeframe)
        raw = (state.get("positions") or {}).get(k)
        if not raw:
            return None
        pos = Position(**raw)
        if pos.status == "ACTIVE":
            return pos
        return None
    except Exception as e:
        logger.error(f"get_active {symbol} error: {e}")
        return None


def lock_new_position(symbol: str, timeframe: str, direction: str, trade_plan: Dict) -> bool:
    try:
        state = _load_state()
        positions = state.setdefault("positions", {})
        k = _key(symbol, timeframe)

        raw = positions.get(k)
        if raw and raw.get("status") == "ACTIVE":
            return False

        pos = Position(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry=float(trade_plan["entry"]),
            sl=float(trade_plan["sl"]),
            tp1=float(trade_plan["tp1"]),
            tp2=float(trade_plan["tp2"]),
            tp3=float(trade_plan["tp3"]),
            status="ACTIVE",
            opened_at=_now_iso(),
        )

        positions[k] = asdict(pos)
        _save_state(state)
        return True
    except Exception as e:
        logger.error(f"lock_new_position {symbol} error: {e}")
        return False


def update_from_price(symbol: str, timeframe: str, price: float) -> Tuple[Optional[Position], Dict]:
    try:
        state = _load_state()
        positions = state.get("positions") or {}
        k = _key(symbol, timeframe)
        raw = positions.get(k)
        if not raw:
            return None, {}

        pos = Position(**raw)
        if pos.status != "ACTIVE":
            return pos, {}

        p = float(price)
        events = {"tp1": False, "tp2": False, "tp3": False, "sl": False, "closed": False, "closed_reason": ""}

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

        positions[k] = asdict(pos)
        state["positions"] = positions
        _save_state(state)
        return pos, events

    except Exception as e:
        logger.error(f"update_from_price {symbol} error: {e}")
        return None, {}
