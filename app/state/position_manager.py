import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


STATE_PATH = Path("positions.json")


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
    status: str  # ACTIVE / CLOSED
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    opened_at: str = ""
    closed_at: str = ""
    closed_reason: str = ""  # "SL" or "TP3"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_state() -> Dict:
    if not STATE_PATH.exists():
        return {"positions": {}}
    with STATE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f) or {"positions": {}}


def _save_state(state: Dict) -> None:
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _key(symbol: str, timeframe: str) -> str:
    return f"{symbol}:{timeframe}".upper()


def get_active(symbol: str, timeframe: str) -> Optional[Position]:
    state = _load_state()
    k = _key(symbol, timeframe)
    raw = (state.get("positions") or {}).get(k)
    if not raw:
        return None
    pos = Position(**raw)
    if pos.status == "ACTIVE":
        return pos
    return None


def lock_new_position(symbol: str, timeframe: str, direction: str, trade_plan: Dict) -> Position:
    """
    Create ACTIVE position and persist immediately.
    Assumes trade_plan has entry/sl/tp1/tp2/tp3 (floats).
    """
    state = _load_state()
    positions = state.setdefault("positions", {})
    k = _key(symbol, timeframe)

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
    return pos


def update_from_price(symbol: str, timeframe: str, price: float) -> Tuple[Optional[Position], Dict]:
    """
    Update TP/SL hits based on current price.
    Returns: (position, events)
      events: {"tp1":bool,"tp2":bool,"tp3":bool,"sl":bool,"closed":bool,"closed_reason":str}
    Unlock only when SL hit OR TP3 hit -> CLOSED.
    """
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

    # LONG
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

    # SHORT
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

    # Close condition (STRICT)
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