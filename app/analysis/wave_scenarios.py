from typing import List, Dict
from app.analysis.wave_rules import validate_impulse, validate_abc


def score_scenario(base_score, warnings, macro_trend, rsi14, volume_spike, direction):
    """
    Scoring model (0-100)
    - base_score: strength from structure type
    - warnings: ลดคะแนนจาก rule/fib warnings
    - macro_trend/rsi/volume: เพิ่ม-ลดความมั่นใจ
    """
    score = float(base_score)

    # warning penalty
    score -= len(warnings) * 4

    # Trend bonus/penalty
    mt = (macro_trend or "NEUTRAL").upper()
    if mt == "NEUTRAL":
        score -= 2
    if mt in ("BULL", "BEAR"):
        score += 4

    # RSI bonus (only strong momentum)
    direction = (direction or "").upper()
    if direction == "LONG":
        if rsi14 >= 60:
            score += 4
        elif rsi14 >= 55:
            score += 2
    elif direction == "SHORT":
        if rsi14 <= 40:
            score += 4
        elif rsi14 <= 45:
            score += 2

    # Volume spike bonus
    if volume_spike:
        score += 5

    return max(min(score, 100), 1)


def normalize_scores(scenarios: List[Dict]) -> List[Dict]:
    total = sum(s["score"] for s in scenarios) or 1.0
    for s in scenarios:
        # ✅ FIX: เปลี่ยนชื่อเป็น relative_score แทน probability
        # เพราะนี่คือสัดส่วนคะแนนเทียบกัน ไม่ใช่ probability จริง
        s["relative_score"] = round((s["score"] / total) * 100, 1)
        s["probability"] = s["relative_score"]  # เก็บไว้กัน backward compat
        s["confidence"] = round(float(s["score"]), 1)
    return scenarios


def build_scenarios(
    pivots: List[Dict],
    macro_trend: str = "NEUTRAL",
    rsi14: float = 50.0,
    volume_spike: bool = False
) -> List[Dict]:
    scenarios = []

    # -------------------------
    # Scenario 1: Impulse LONG
    # -------------------------
    if len(pivots) >= 6:
        last6 = pivots[-6:]
        ok, warnings = validate_impulse(last6, "LONG")
        if ok and len(warnings) <= 1:

            scenarios.append({
                "type": "IMPULSE_LONG",
                "phase": "Wave 5 or continuation",
                "direction": "LONG",
                "score": score_scenario(85, warnings, macro_trend, rsi14, volume_spike, direction="LONG"),
                "reasons": warnings,
                "pivots": last6,
            })

    # -------------------------
    # Scenario 2: Impulse SHORT
    # -------------------------
    if len(pivots) >= 6:
        last6 = pivots[-6:]
        ok, warnings = validate_impulse(last6, "SHORT")
        if ok and len(warnings) <= 1:

            scenarios.append({
                "type": "IMPULSE_SHORT",
                "phase": "Wave 5 or continuation",
                "direction": "SHORT",
                "score": score_scenario(85, warnings, macro_trend, rsi14, volume_spike, direction="SHORT"),
                "reasons": warnings,
                "pivots": last6,
            })

    # -------------------------
    # Scenario 3: ABC Correction
    # -------------------------
    if len(pivots) >= 4:
        last4 = pivots[-4:]

        ok_down, warnings_down = validate_abc(last4, "DOWN")
        if ok_down and len(warnings_down) <= 1:
            scenarios.append({
                "type": "ABC_DOWN",
                "phase": "Wave C ลง",
                "direction": "SHORT",
                "score": score_scenario(65, warnings_down, macro_trend, rsi14, volume_spike, direction="SHORT"),
                "reasons": warnings_down,
                "pivots": last4,
            })

        ok_up, warnings_up = validate_abc(last4, "UP")
        if ok_up and len(warnings_up) <= 1:
            scenarios.append({
                "type": "ABC_UP",
                "phase": "Wave C ขึ้น",
                "direction": "LONG",
                "score": score_scenario(65, warnings_up, macro_trend, rsi14, volume_spike, direction="LONG"),
                "reasons": warnings_up,
                "pivots": last4,
            })

    if not scenarios:
        return []

    scenarios.sort(key=lambda x: x["score"], reverse=True)
    scenarios = scenarios[:3]
    scenarios = normalize_scores(scenarios)
    return scenarios