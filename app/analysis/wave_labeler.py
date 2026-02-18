from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.analysis.wave_rules import validate_impulse, validate_abc


@dataclass
class WaveLabel:
    pattern: str               # "IMPULSE_LONG" / "IMPULSE_SHORT" / "ABC_UP" / "ABC_DOWN"
    direction: str             # "LONG" / "SHORT"
    start_index: int           # pivot-chain start (0-based in pivots list)
    end_index: int             # pivot-chain end
    pivot_count: int           # 6 for impulse, 4 for abc
    confidence: float          # 0-100 (ใช้ score แบบเบื้องต้นจากกฎที่ผ่าน)
    reasons: List[str]         # รายการเหตุผล/คำเตือน (ถ้ามี)
    pivots: List[Dict]         # pivots slice ที่ใช้


def _score_from_reasons(base: float, reasons: List[str]) -> float:
    # ยิ่งมี reasons มาก = ความมั่นใจลด (แต่ ABC อนุญาต warning ได้)
    score = float(base) - (len(reasons) * 5.0)
    if score < 1:
        score = 1.0
    if score > 100:
        score = 100.0
    return score


def label_pivot_chain(pivots: List[Dict]) -> Dict:
    """
    สแกน pivot chain ทั้งเส้น แล้วหา pattern ที่ "จบล่าสุด" (ใกล้ท้ายที่สุด)
    คืนค่า label เดียวที่ดีที่สุด (หรือ None)
    - IMPULSE ใช้ 6 pivots
    - ABC ใช้ 4 pivots
    """

    if not pivots or len(pivots) < 4:
        return {"label": None, "matches": []}

    matches: List[WaveLabel] = []

    # --- Scan IMPULSE windows (6 pivots) ---
    if len(pivots) >= 6:
        for i in range(0, len(pivots) - 6 + 1):
            window = pivots[i : i + 6]

            okL, reasonsL = validate_impulse(window, "LONG")
            if okL:
                matches.append(
                    WaveLabel(
                        pattern="IMPULSE_LONG",
                        direction="LONG",
                        start_index=i,
                        end_index=i + 5,
                        pivot_count=6,
                        confidence=_score_from_reasons(85.0, reasonsL),
                        reasons=reasonsL,
                        pivots=window,
                    )
                )

            okS, reasonsS = validate_impulse(window, "SHORT")
            if okS:
                matches.append(
                    WaveLabel(
                        pattern="IMPULSE_SHORT",
                        direction="SHORT",
                        start_index=i,
                        end_index=i + 5,
                        pivot_count=6,
                        confidence=_score_from_reasons(85.0, reasonsS),
                        reasons=reasonsS,
                        pivots=window,
                    )
                )

    # --- Scan ABC windows (4 pivots) ---
    for i in range(0, len(pivots) - 4 + 1):
        window = pivots[i : i + 4]

        okD, reasonsD = validate_abc(window, "DOWN")
        if okD:
            matches.append(
                WaveLabel(
                    pattern="ABC_DOWN",
                    direction="SHORT",
                    start_index=i,
                    end_index=i + 3,
                    pivot_count=4,
                    confidence=_score_from_reasons(65.0, reasonsD),
                    reasons=reasonsD,
                    pivots=window,
                )
            )

        okU, reasonsU = validate_abc(window, "UP")
        if okU:
            matches.append(
                WaveLabel(
                    pattern="ABC_UP",
                    direction="LONG",
                    start_index=i,
                    end_index=i + 3,
                    pivot_count=4,
                    confidence=_score_from_reasons(65.0, reasonsU),
                    reasons=reasonsU,
                    pivots=window,
                )
            )

    if not matches:
        return {"label": None, "matches": []}

    # เลือก "จบล่าสุด" ก่อน (end_index มากสุด) แล้วค่อยตัดสินด้วย confidence
    matches.sort(key=lambda m: (m.end_index, m.confidence), reverse=True)
    best = matches[0]

    # ทำผลลัพธ์ให้อ่านง่าย
    label = {
        "pattern": best.pattern,
        "direction": best.direction,
        "start_pivot_i": best.start_index,
        "end_pivot_i": best.end_index,
        "pivot_count": best.pivot_count,
        "confidence": round(float(best.confidence), 1),
        "reasons": best.reasons,
        # ✅ ส่ง pivot prices มาด้วย (ย่อ)
        "pivots": [
            {
                "index": int(p.get("index")),
                "type": p.get("type"),
                "price": float(p.get("price")),
            }
            for p in (best.pivots or [])
        ],
    }

    return {"label": label, "matches": matches}
