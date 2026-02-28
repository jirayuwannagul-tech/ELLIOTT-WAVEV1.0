from __future__ import annotations

from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

from app.analysis.wave_rules import validate_impulse, validate_abc

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _p(pivots: List[Dict], i: int) -> float:
    return float(pivots[i]["price"])


def _degree(pivots: List[Dict], i: int) -> str:
    return str(pivots[i].get("degree", "minor"))


def _fib_ratio(a: float, b: float, c: float) -> Optional[float]:
    move = abs(b - a)
    if move == 0:
        return None
    return abs(c - b) / move


def _in_fib_zone(ratio: float, zones: List[float], tolerance: float = 0.05) -> bool:
    return any(abs(ratio - z) <= tolerance for z in zones)


# ─────────────────────────────────────────────
# STEP 1: หา Major Trend
# ─────────────────────────────────────────────

def _find_major_structure(pivots: List[Dict]) -> Dict:
    if not pivots:
        return {}

    intermediate = [p for p in pivots if _degree([p], 0) == "intermediate"]
    if len(intermediate) < 4:
        intermediate = pivots

    highs = [p for p in intermediate if p["type"] == "H"]
    lows  = [p for p in intermediate if p["type"] == "L"]

    if not highs or not lows:
        return {}

    major_high = max(highs, key=lambda p: p["price"])
    major_low  = min(lows,  key=lambda p: p["price"])

    major_high_idx = next(i for i, p in enumerate(intermediate) if p["price"] == major_high["price"])
    major_low_idx  = next(i for i, p in enumerate(intermediate) if p["price"] == major_low["price"])
    last_idx       = len(intermediate) - 1

    if major_high_idx > major_low_idx:
        price_from_high = (major_high["price"] - intermediate[last_idx]["price"]) / major_high["price"]
        if price_from_high > 0.15:
            major_trend = "DOWNTREND"
        elif price_from_high > 0.05:
            major_trend = "RANGING"
        else:
            major_trend = "UPTREND"
    else:
        price_from_low = (intermediate[last_idx]["price"] - major_low["price"]) / major_low["price"]
        if price_from_low > 0.15:
            major_trend = "UPTREND"
        elif price_from_low > 0.05:
            major_trend = "RANGING"
        else:
            major_trend = "DOWNTREND"

    recent_window = intermediate[-20:] if len(intermediate) >= 20 else intermediate
    recent_highs  = [p for p in recent_window if p["type"] == "H"]
    recent_lows   = [p for p in recent_window if p["type"] == "L"]

    return {
        "major_high": major_high,
        "major_low":  major_low,
        "recent_high": recent_highs[-1] if recent_highs else highs[-1],
        "recent_low":  recent_lows[-1]  if recent_lows  else lows[-1],
        "major_trend": major_trend,
        "intermediate_pivots": intermediate,
    }


# ─────────────────────────────────────────────
# STEP 2: นับคลื่น Elliott Wave จริงๆ
# ─────────────────────────────────────────────

def _find_impulse_sequence(
    pivots: List[Dict],
    direction: str,
) -> Optional[Dict]:
    """
    หา 5-wave impulse sequence ที่ valid ที่สุด
    สแกนจาก pivot ล่าสุดย้อนกลับไป
    """
    direction = direction.upper()

    best_result = None

    # สแกนจากล่าสุดย้อนไป หา window 6 pivot ที่ผ่าน EW rules
    for i in range(len(pivots) - 6, max(-1, len(pivots) - 30), -1):
        window = pivots[i: i + 6]
        if len(window) < 6:
            continue

        ok, warnings = validate_impulse(window, direction)
        if ok:
            best_result = {
                "pivots": window,
                "start_idx": i,
                "warnings": warnings,
                "quality": len(warnings),  # น้อย = ดีกว่า
            }
            break  # เอาล่าสุดที่ valid

    return best_result


def _find_abc_sequence(
    pivots: List[Dict],
    direction: str,
) -> Optional[Dict]:
    """
    หา ABC correction sequence ที่ valid ที่สุด
    direction: "UP" = bullish ABC (long setup), "DOWN" = bearish ABC (short setup)
    """
    direction = direction.upper()

    for i in range(len(pivots) - 4, max(-1, len(pivots) - 20), -1):
        window = pivots[i: i + 4]
        if len(window) < 4:
            continue

        ok, warnings = validate_abc(window, direction)
        if ok:
            return {
                "pivots": window,
                "start_idx": i,
                "warnings": warnings,
                "quality": len(warnings),
            }

    return None

def _determine_wave_position(
    pivots: List[Dict],
    structure: Dict,
    primary_context: Optional[Dict] = None,
) -> Dict:
    if not pivots or len(pivots) < 6:
        return {"position": "UNKNOWN", "entry_type": None}

    major_trend = structure.get("major_trend", "UNKNOWN")
    if major_trend == "UNKNOWN":
        return {"position": "UNKNOWN", "entry_type": None}

    last_pivot = pivots[-1]

    # ── clean pivots ให้ H/L สลับกันก่อน ──
    clean: List[Dict] = []
    for p in pivots:
        if not clean:
            clean.append(p)
            continue
        if p["type"] == clean[-1]["type"]:
            # เอา extreme
            if p["type"] == "H" and p["price"] > clean[-1]["price"]:
                clean[-1] = p
            elif p["type"] == "L" and p["price"] < clean[-1]["price"]:
                clean[-1] = p
        else:
            clean.append(p)
    pivots = clean

    # ─────────────────────────────────────────────
    # STEP 1: หา impulse sequence จริงๆ ด้วย validate_impulse
    # สแกนจาก pivot ล่าสุดย้อนหลังไป
    # ─────────────────────────────────────────────

    direction_to_scan = "LONG" if major_trend == "UPTREND" else "SHORT"
    found_impulse = None

    for i in range(len(pivots) - 6, max(-1, len(pivots) - 40), -1):
        window = pivots[i: i + 6]
        if len(window) < 6:
            continue
        ok, warnings = validate_impulse(window, direction_to_scan)
        if ok:
            found_impulse = {
                "pivots": window,
                "w1_start": window[0]["price"],
                "w1_end":   window[1]["price"],
                "w2_end":   window[2]["price"],
                "w3_end":   window[3]["price"],
                "w4_end":   window[4]["price"],
                "w5_end":   window[5]["price"],
                "direction": direction_to_scan,
            }
            break

    # ─────────────────────────────────────────────
    # STEP 2: ถ้าเจอ impulse → ดูว่า pivot ล่าสุดอยู่หลัง wave ไหน
    # ─────────────────────────────────────────────

    if found_impulse:
        w = found_impulse
        imp_pivots = w["pivots"]
        last_imp_idx = imp_pivots[-1].get("index", 0)
        last_pivot_idx = last_pivot.get("index", 999)

        # pivot ล่าสุดอยู่หลัง impulse จบ = คาด ABC correction
        if last_pivot_idx > last_imp_idx:
            abc_dir = "DOWN" if direction_to_scan == "LONG" else "UP"
            abc = _find_abc_sequence(pivots, abc_dir)
            if abc:
                abc_pivots = abc["pivots"]
                a_len = abs(abc_pivots[1]["price"] - abc_pivots[0]["price"])
                c_len = abs(abc_pivots[3]["price"] - abc_pivots[2]["price"])
                c_ext = c_len / a_len if a_len > 0 else 0
                entry_dir = "LONG" if direction_to_scan == "LONG" else "SHORT"
                return {
                    "position": "WAVE_C_END_LONG" if entry_dir == "LONG" else "WAVE_C_END_SHORT",
                    "entry_type": "ABC",
                    "direction": entry_dir,
                    "fib_ratio": c_ext,
                    "wave_1_start": w["w1_start"],
                    "wave_5_end": w["w5_end"],
                    "note": f"Impulse จบ wave 5 แล้ว — ABC correction C={c_ext:.2f}x A",
                }

        # pivot ล่าสุดอยู่ใน impulse หรือหลัง wave 2
        # ดูว่าอยู่ใน wave 2 หรือ wave 4
        w2_pivot = imp_pivots[2]
        w4_pivot = imp_pivots[4]

        # ถ้า last pivot ใกล้กับ w2 หรือ w4
        if abs(last_pivot.get("index", 0) - w2_pivot.get("index", 0)) <= 3:
            fib = _fib_ratio(w["w1_start"], w["w1_end"], w["w2_end"])
            return {
                "position": "IN_WAVE_2",
                "entry_type": "IMPULSE",
                "direction": "LONG" if direction_to_scan == "LONG" else "SHORT",
                "fib_ratio": fib if fib else 0.0,
                "wave_1_start": w["w1_start"],
                "wave_1_end":   w["w1_end"],
                "note": f"IN Wave 2 retrace {fib:.1%} — เตรียม {'LONG' if direction_to_scan == 'LONG' else 'SHORT'} wave 3",
            }

        if abs(last_pivot.get("index", 0) - w4_pivot.get("index", 0)) <= 3:
            fib = _fib_ratio(w["w3_end"], w["w4_end"], w["w4_end"])
            return {
                "position": "IN_WAVE_4",
                "entry_type": "IMPULSE",
                "direction": "LONG" if direction_to_scan == "LONG" else "SHORT",
                "fib_ratio": fib if fib else 0.0,
                "wave_3_end": w["w3_end"],
                "wave_4_end": w["w4_end"],
                "note": f"IN Wave 4 retrace — เตรียม {'LONG' if direction_to_scan == 'LONG' else 'SHORT'} wave 5",
            }

    # ─────────────────────────────────────────────
    # STEP 3: Fallback — ถ้าหา impulse ไม่เจอ ใช้ fib จาก major structure
    # ─────────────────────────────────────────────

    highs = [p for p in pivots if p["type"] == "H"]
    lows  = [p for p in pivots if p["type"] == "L"]
    major_high_price = structure.get("major_high", {}).get("price", 0)
    major_low_price  = structure.get("major_low",  {}).get("price", 0)

    if major_trend == "UPTREND":
        if last_pivot["type"] == "L" and len(lows) >= 2 and len(highs) >= 1:
            if lows[-1]["price"] > lows[-2]["price"]:
                swing_low  = lows[-2]["price"]
                swing_high = highs[-1]["price"]
                current    = last_pivot["price"]
                if swing_high > swing_low:
                    ratio = _fib_ratio(swing_low, swing_high, current)
                    if ratio is not None:
                        if _in_fib_zone(ratio, [0.5, 0.618, 0.786], tolerance=0.06):
                            return {
                                "position": "IN_WAVE_2",
                                "entry_type": "IMPULSE",
                                "direction": "LONG",
                                "fib_ratio": ratio,
                                "wave_1_start": swing_low,
                                "wave_1_end": swing_high,
                                "note": f"Wave 2 pullback {ratio:.1%} — เตรียม LONG wave 3",
                            }
                        elif _in_fib_zone(ratio, [0.236, 0.382], tolerance=0.06):
                            return {
                                "position": "IN_WAVE_4",
                                "entry_type": "IMPULSE",
                                "direction": "LONG",
                                "fib_ratio": ratio,
                                "wave_3_end": swing_high,
                                "note": f"Wave 4 pullback {ratio:.1%} — เตรียม LONG wave 5",
                            }

    elif major_trend == "DOWNTREND":
        if last_pivot["type"] == "H" and major_high_price > 0 and major_low_price > 0:
            current    = last_pivot["price"]
            swing_size = major_high_price - major_low_price
            if swing_size > 0 and current < major_high_price:
                ratio = (current - major_low_price) / swing_size
                if _in_fib_zone(ratio, [0.5, 0.618, 0.786], tolerance=0.08):
                    return {
                        "position": "IN_WAVE_2",
                        "entry_type": "IMPULSE",
                        "direction": "SHORT",
                        "fib_ratio": ratio,
                        "wave_1_start": major_high_price,
                        "wave_1_end": major_low_price,
                        "note": f"Wave 2 bounce {ratio:.1%} — เตรียม SHORT wave 3",
                    }
                elif _in_fib_zone(ratio, [0.236, 0.382], tolerance=0.08):
                    return {
                        "position": "IN_WAVE_4",
                        "entry_type": "IMPULSE",
                        "direction": "SHORT",
                        "fib_ratio": ratio,
                        "wave_3_end": major_low_price,
                        "note": f"Wave 4 bounce {ratio:.1%} — เตรียม SHORT wave 5",
                    }

        if last_pivot["type"] == "L" and len(lows) >= 2 and len(highs) >= 1:
            if lows[-1]["price"] < lows[-2]["price"]:
                prev_high  = highs[-1]["price"]
                current    = last_pivot["price"]
                swing_size = prev_high - current
                if swing_size > 0:
                    return {
                        "position": "IN_WAVE_2",
                        "entry_type": "IMPULSE",
                        "direction": "SHORT",
                        "fib_ratio": 0.0,
                        "wave_1_start": prev_high,
                        "wave_1_end": current,
                        "bounce_50":  current + swing_size * 0.5,
                        "bounce_618": current + swing_size * 0.618,
                        "note": "Lower Low confirmed — รอ bounce 50-61.8% แล้ว SHORT",
                    }
            elif lows[-1]["price"] > lows[-2]["price"]:
                prev_high = highs[-1]["price"]
                current   = last_pivot["price"]
                ratio = _fib_ratio(lows[-2]["price"], prev_high, current)
                return {
                    "position": "IN_WAVE_4",
                    "entry_type": "IMPULSE",
                    "direction": "SHORT",
                    "fib_ratio": ratio if ratio else 0.0,
                    "note": "Wave 4 bounce ใน downtrend — เตรียม SHORT wave 5",
                }

    elif major_trend == "RANGING":
        recent_high = structure.get("recent_high")
        recent_low  = structure.get("recent_low")
        if recent_high and recent_low:
            range_size = recent_high["price"] - recent_low["price"]
            if range_size > 0:
                current = last_pivot["price"]
                if last_pivot["type"] == "L":
                    pos = (current - recent_low["price"]) / range_size
                    if pos <= 0.25:
                        return {
                            "position": "RANGE_BOTTOM",
                            "entry_type": "ABC",
                            "direction": "LONG",
                            "fib_ratio": pos,
                            "note": "ราคาใกล้ขอบล่าง range — LONG",
                        }
                if last_pivot["type"] == "H":
                    pos = (recent_high["price"] - current) / range_size
                    if pos <= 0.25:
                        return {
                            "position": "RANGE_TOP",
                            "entry_type": "ABC",
                            "direction": "SHORT",
                            "fib_ratio": pos,
                            "note": "ราคาใกล้ขอบบน range — SHORT",
                        }

    return {"position": "UNKNOWN", "entry_type": None}

# ─────────────────────────────────────────────
# STEP 3: Score
# ─────────────────────────────────────────────

def score_scenario(
    base_score: float,
    warnings: List[str],
    macro_trend: str,
    rsi14: float,
    volume_spike: bool,
    direction: str,
    fib_ratio: Optional[float] = None,
    position: str = "UNKNOWN",
) -> float:
    score = float(base_score)
    score -= len(warnings) * 4

    mt = (macro_trend or "NEUTRAL").upper()
    direction = (direction or "").upper()

    if mt == "BULL" and direction == "LONG":
        score += 6
    elif mt == "BEAR" and direction == "SHORT":
        score += 6
    elif mt == "NEUTRAL":
        score -= 2

    if direction == "LONG":
        if 40 <= rsi14 <= 60:
            score += 4
        elif rsi14 < 35:
            score += 3
        elif rsi14 > 70:
            score -= 4
    elif direction == "SHORT":
        if 40 <= rsi14 <= 60:
            score += 4
        elif rsi14 > 65:
            score += 3
        elif rsi14 < 30:
            score -= 4

    if volume_spike:
        score += 5

    if fib_ratio is not None:
        if _in_fib_zone(fib_ratio, [0.618], tolerance=0.02):
            score += 6
        elif _in_fib_zone(fib_ratio, [0.5, 0.786], tolerance=0.02):
            score += 3

    # Wave 2 = high probability (wave 3 มักแรงที่สุด)
    if "WAVE_2" in position or "IN_WAVE_2" in position:
        score += 6
    elif "WAVE_4" in position or "IN_WAVE_4" in position:
        score += 3
    elif "WAVE_C" in position:
        score += 4

    return max(min(score, 100), 1)


# ─────────────────────────────────────────────
# STEP 4: Normalize
# ─────────────────────────────────────────────

def normalize_scores(scenarios: List[Dict]) -> List[Dict]:
    total = sum(s["score"] for s in scenarios) or 1.0
    for s in scenarios:
        s["relative_score"] = round((s["score"] / total) * 100, 1)
        s["probability"]    = s["relative_score"]
        s["confidence"]     = round(float(s["score"]), 1)
    return scenarios


# ─────────────────────────────────────────────
# MAIN: build_scenarios
# ─────────────────────────────────────────────

def build_scenarios(
    pivots: List[Dict],
    macro_trend: str = "NEUTRAL",
    rsi14: float = 50.0,
    volume_spike: bool = False,
) -> List[Dict]:
    scenarios: List[Dict] = []

    if not pivots or len(pivots) < 4:
        return []

    # ── Step 1: Primary Wave bias จาก btc_cycle ──
    primary: Dict = {}
    try:
        from app.analysis.btc_cycle import get_primary_bias
        primary = get_primary_bias()
    except Exception:
        pass

    primary_bias        = primary.get("bias", "NEUTRAL")
    primary_note        = primary.get("note", "")
    primary_fib_targets = primary.get("fib_targets", {})
    primary_wave        = primary.get("wave", "?")
    primary_degree      = primary.get("degree", "?")

    # ── Step 2: Major structure จาก 1D ──
    structure   = _find_major_structure(pivots)
    major_trend = structure.get("major_trend", "UNKNOWN")

    if major_trend == "UNKNOWN":
        return []

    # ── Step 3: Wave position จาก 1D ──
    wave_pos = _determine_wave_position(pivots, structure, primary_context=primary)
    position   = wave_pos.get("position", "UNKNOWN")
    entry_type = wave_pos.get("entry_type")
    direction  = wave_pos.get("direction")
    fib_ratio  = wave_pos.get("fib_ratio")
    note       = wave_pos.get("note", "")

    if position == "UNKNOWN" or not entry_type or not direction:
        return []

    # ── Step 4: Filter ด้วย Primary Wave bias ──
    warnings = []

    # ถ้า primary BEARISH → ไม่ Long
    if primary_bias == "BEARISH" and direction == "LONG":
        warnings.append(f"สวน Primary Wave {primary_wave} ({primary_degree}) — BEARISH")
    # ถ้า primary BULLISH → ไม่ SHORT
    elif primary_bias == "BULLISH" and direction == "SHORT":
        warnings.append(f"สวน Primary Wave {primary_wave} ({primary_degree}) — BULLISH")

    # ถ้าสวน primary wave อย่างชัดเจน → ไม่เทรด
    if len(warnings) > 0 and primary_bias != "NEUTRAL":
        # ยังเทรดได้ถ้า 1D trend แรงมากพอ แต่ลด score
        pass

    mt = (macro_trend or "NEUTRAL").upper()
    if mt == "BULL" and direction == "SHORT":
        warnings.append("สวน macro trend (BULL)")
    elif mt == "BEAR" and direction == "LONG":
        warnings.append("สวน macro trend (BEAR)")

    # ── Step 5: สร้าง scenario ──
    if entry_type == "IMPULSE":
        base_score = 82
        sc_type    = "IMPULSE_LONG" if direction == "LONG" else "IMPULSE_SHORT"
        phase      = note or f"{position} — Impulse"
    else:
        base_score = 68
        sc_type    = "ABC_UP" if direction == "LONG" else "ABC_DOWN"
        phase      = note or f"{position} — ABC"

    score = score_scenario(
        base_score, warnings, macro_trend, rsi14,
        volume_spike, direction,
        fib_ratio=fib_ratio, position=position,
    )

    # Primary wave alignment bonus/penalty
    if primary_bias == "BEARISH" and direction == "SHORT":
        score = min(score + 8, 100)   # สอดคล้อง primary → bonus
    elif primary_bias == "BULLISH" and direction == "LONG":
        score = min(score + 8, 100)
    elif primary_bias != "NEUTRAL":
        score = max(score - 10, 1)    # สวน primary → penalty

    reasons = [
        f"Primary Wave: {primary_wave} ({primary_degree}) — {primary_bias}",
        f"Wave position: {position}",
    ]
    if note:
        reasons.append(note)
    if fib_ratio is not None and fib_ratio > 0:
        reasons.append(f"Fib: {fib_ratio:.3f}")
    reasons.append(f"Major trend: {major_trend}")
    if primary_fib_targets:
        targets_str = " | ".join([f"{k}={int(v):,}" for k, v in primary_fib_targets.items()])
        reasons.append(f"Primary targets: {targets_str}")
    if warnings:
        reasons.extend(warnings)

    scenario = {
        "type":           sc_type,
        "phase":          phase,
        "direction":      direction,
        "score":          score,
        "reasons":        reasons,
        "pivots":         pivots,
        "major_trend":    major_trend,
        "wave_position":  position,
        "fib_ratio":      fib_ratio,
        "swing_high":     wave_pos.get("wave_1_start") or wave_pos.get("wave_3_end"),
        "swing_low":      wave_pos.get("wave_1_end")   or wave_pos.get("wave_4_low"),
        "primary_wave":   primary_wave,
        "primary_bias":   primary_bias,
        "primary_note":   primary_note,
        "is_fallback":    False,
    }

    if score >= 50:
        scenarios.append(scenario)

    if not scenarios:
        return []

    scenarios.sort(key=lambda x: x["score"], reverse=True)
    return normalize_scores(scenarios[:3])