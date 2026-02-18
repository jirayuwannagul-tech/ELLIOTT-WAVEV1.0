from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.analysis.pivot import find_fractal_pivots, filter_pivots


@dataclass
class Zone:
    kind: str            # "SR"
    level: float         # center price
    low: float           # zone low
    high: float          # zone high
    touches: int         # number of hits clustered
    side: str            # "SUPPORT" or "RESIST"
    notes: str = ""


def _safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _merge_clusters(levels: List[float], tol_pct: float) -> List[List[float]]:
    """
    cluster ราคาที่อยู่ใกล้กันภายใน tol_pct ของ level
    ใช้ center ของ cluster แรกเป็น anchor เพื่อป้องกัน cluster drift
    """
    if not levels:
        return []
    levels = sorted(float(x) for x in levels)
    clusters: List[List[float]] = [[levels[0]]]
    # FIX: เก็บ anchor (center เริ่มต้น) แยกต่างหาก
    anchors: List[float] = [levels[0]]

    for v in levels[1:]:
        anchor = anchors[-1]
        tol = abs(anchor) * (tol_pct / 100.0)
        if abs(v - anchor) <= tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
            anchors.append(v)

    return clusters


def build_zones_from_pivots(
    df: pd.DataFrame,
    min_pct_move: float = 1.5,
    tol_pct: float = 0.35,
    min_touches: int = 2,
    max_zones: int = 8,
) -> List[Dict]:
    """
    - หา pivots จาก fractal
    - เอา pivot prices มาคลัสเตอร์เป็นโซน
    - โซนที่ touches สูงจะสำคัญกว่า
    """
    if df is None or len(df) < 50:
        return []

    close = _safe_float(df["close"].iloc[-1], 0.0)

    pivots = find_fractal_pivots(df, left=2, right=2)
    pivots = filter_pivots(pivots, min_pct_move=min_pct_move)

    highs = [float(p["price"]) for p in pivots if p.get("type") == "H"]
    lows = [float(p["price"]) for p in pivots if p.get("type") == "L"]

    high_clusters = _merge_clusters(highs, tol_pct=tol_pct)
    low_clusters = _merge_clusters(lows, tol_pct=tol_pct)

    zones: List[Zone] = []

    def _cluster_to_zone(cluster: List[float], side: str) -> Optional[Zone]:
        if not cluster or len(cluster) < min_touches:
            return None

        center = sum(cluster) / len(cluster)
        # FIX: ใช้ lo/hi ตรง ๆ แทนการคำนวณซ้ำจาก spread
        lo = min(cluster)
        hi = max(cluster)
        # เผื่อ cluster มีแค่ 1 ค่า (กรณีผ่าน min_touches=1) ให้มี spread เล็กน้อย
        if hi == lo:
            margin = abs(center) * 0.0005
            lo = center - margin
            hi = center + margin

        return Zone(
            kind="SR",
            level=round(center, 6),
            low=round(lo, 6),
            high=round(hi, 6),
            touches=len(cluster),
            side=side,
            notes=f"cluster[{len(cluster)}]",
        )

    for c in high_clusters:
        z = _cluster_to_zone(c, side="RESIST")
        if z:
            zones.append(z)

    for c in low_clusters:
        z = _cluster_to_zone(c, side="SUPPORT")
        if z:
            zones.append(z)

    def _score(z: Zone) -> Tuple[int, float]:
        dist = abs(float(z.level) - close) if close else 1e9
        return (z.touches, -dist)

    zones.sort(key=_score, reverse=True)
    zones = zones[:max_zones]

    return [z.__dict__ for z in zones]


def nearest_support_resist(zones: list, price: float) -> dict:
    """
    คืน SR ใกล้สุดใต้/เหนือราคา
    ไม่เชื่อ side เดิม — คำนวณใหม่จากตำแหน่งราคา
    """
    price = float(price)

    below = []
    above = []

    for z in (zones or []):
        lvl = float(z.get("level", 0) or 0)
        # FIX: strict comparison เพื่อไม่ให้ level เดียวกับ price
        # ปรากฏในทั้ง support และ resist พร้อมกัน
        if lvl < price:
            below.append(z)
        elif lvl > price:
            above.append(z)

    below.sort(key=lambda z: abs(float(z.get("level", 0) or 0) - price))
    above.sort(key=lambda z: abs(float(z.get("level", 0) or 0) - price))

    sup = dict(below[0]) if below else None
    res = dict(above[0]) if above else None

    if sup:
        sup["side"] = "SUPPORT"
    if res:
        res["side"] = "RESIST"

    return {
        "support": sup,
        "resist": res,
    }