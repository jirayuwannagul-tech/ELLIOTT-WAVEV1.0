from typing import List, Dict
from app.analysis.wave_rules import validate_impulse, validate_abc


def score_scenario(base_score, warnings, macro_trend, rsi14, volume_spike, direction):
    score = float(base_score)

    score -= len(warnings) * 4

    mt = (macro_trend or "NEUTRAL").upper()
    if mt == "NEUTRAL":
        score -= 2
    if mt in ("BULL", "BEAR"):
        score += 4

    direction = (direction or "").upper()

    # ✅ แก้: bonus เมื่อ RSI อยู่ใน setup zone ไม่ใช่ extended zone
    if direction == "LONG":
        if 45 <= rsi14 <= 60:   # midrange momentum ดี
            score += 4
        elif 40 <= rsi14 < 45:  # กำลัง recover
            score += 2
        elif rsi14 > 70:        # overbought — penalty
            score -= 4
    elif direction == "SHORT":
        if 40 <= rsi14 <= 55:   # midrange momentum ดี
            score += 4
        elif 55 < rsi14 <= 60:  # กำลัง weaken
            score += 2
        elif rsi14 < 30:        # oversold — penalty
            score -= 4

    if volume_spike:
        score += 5

    return max(min(score, 100), 1)

def normalize_scores(scenarios: List[Dict]) -> List[Dict]:
    total = sum(s["score"] for s in scenarios) or 1.0
    for s in scenarios:
        s["relative_score"] = round((s["score"] / total) * 100, 1)
        s["probability"] = s["relative_score"]  # backward compat
        s["confidence"] = round(float(s["score"]), 1)
    return scenarios

def build_scenarios(
    pivots: List[Dict],
    macro_trend: str = "NEUTRAL",
    rsi14: float = 50.0,
    volume_spike: bool = False
) -> List[Dict]:
    scenarios: List[Dict] = []

    # Scenario 1: Impulse LONG
    if len(pivots) >= 6:
        last6 = pivots[-6:]
        ok, warnings = validate_impulse(last6, "LONG")
        if ok:
            scenarios.append({
                "type": "IMPULSE_LONG",
                "phase": "Wave 5 or continuation",
                "direction": "LONG",
                "score": score_scenario(85, warnings, macro_trend, rsi14, volume_spike, direction="LONG"),
                "reasons": warnings,
                "pivots": last6,
            })

    # Scenario 2: Impulse SHORT
    if len(pivots) >= 6:
        last6 = pivots[-6:]
        ok, warnings = validate_impulse(last6, "SHORT")
        if ok:
            scenarios.append({
                "type": "IMPULSE_SHORT",
                "phase": "Wave 5 or continuation",
                "direction": "SHORT",
                "score": score_scenario(85, warnings, macro_trend, rsi14, volume_spike, direction="SHORT"),
                "reasons": warnings,
                "pivots": last6,
            })

    # Scenario 3: ABC Correction
    if len(pivots) >= 4:
        last4 = pivots[-4:]

        ok_down, warnings_down = validate_abc(last4, "DOWN")
        if ok_down:
            scenarios.append({
                "type": "ABC_DOWN",
                "phase": "Wave C ลง",
                "direction": "SHORT",
                "score": score_scenario(65, warnings_down, macro_trend, rsi14, volume_spike, direction="SHORT"),
                "reasons": warnings_down,
                "pivots": last4,
            })

        ok_up, warnings_up = validate_abc(last4, "UP")
        if ok_up:
            scenarios.append({
                "type": "ABC_UP",
                "phase": "Wave C ขึ้น",
                "direction": "LONG",
                "score": score_scenario(65, warnings_up, macro_trend, rsi14, volume_spike, direction="LONG"),
                "reasons": warnings_up,
                "pivots": last4,
            })

    # ✅ FIX: ถ้าไม่มี scenario แต่มี pivots พอแล้ว -> สร้าง fallback ขั้นต่ำ
    # เพื่อไม่ให้ scenarios=0 (ให้ระบบไปตัด READY/BLOCKED ใน wave_engine แทน)
    if not scenarios and len(pivots) >= 4:
        last4 = pivots[-4:]
        fb_reasons = ["fallback: rules not satisfied yet (keep watching)"]

        # ✅ FIX: ลดคะแนน fallback ให้ต่ำกว่า threshold ทุกกรณี (watchlist only)
        scenarios.append({
            "type": "ABC_UP",
            "phase": "Fallback (watchlist only)",
            "direction": "LONG",
            "score": score_scenario(
                30,
                fb_reasons,
                macro_trend,
                rsi14,
                volume_spike,
                "LONG",
            ),
            "reasons": fb_reasons,
            "pivots": last4,
            "is_fallback": True,
        })

        scenarios.append({
            "type": "ABC_DOWN",
            "phase": "Fallback (watchlist only)",
            "direction": "SHORT",
            "score": score_scenario(
                30,
                fb_reasons,
                macro_trend,
                rsi14,
                volume_spike,
                "SHORT",
            ),
            "reasons": fb_reasons,
            "pivots": last4,
            "is_fallback": True,
        })

    if not scenarios:
        return []

    scenarios.sort(key=lambda x: x["score"], reverse=True)
    scenarios = scenarios[:3]
    return normalize_scores(scenarios)