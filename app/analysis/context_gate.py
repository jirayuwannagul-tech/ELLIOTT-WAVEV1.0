from typing import Dict, Optional

def apply_context_gate(
    scenario: Dict,
    macro_bias: Dict,
    min_confidence: float = 60.0,
) -> Optional[Dict]:
    """
    Gate layer (Strict Trend-Following - Option A):
    - ตัดสวน macro trend ทิ้ง
    - ตัด confidence ต่ำกว่า threshold
    - แนบ debug fields: allowed/reason/context_score (แต่ยังคืน scenario เดิม)
    """

    direction = (scenario.get("direction") or "").upper()
    conf = float(scenario.get("confidence") or scenario.get("score") or 0)

    # --- ใช้โครง macro_bias ที่มีอยู่ในระบบคุณ ---
    bias = (macro_bias.get("bias") or "NEUTRAL").upper()
    bias_strength = float(macro_bias.get("strength") or 0)
    allow_long = bool(macro_bias.get("allow_long", True))
    allow_short = bool(macro_bias.get("allow_short", True))

    allowed = True
    reason = ""

    # ---- confidence filter ----
    if conf < min_confidence:
        allowed = False
        reason = f"LOW_CONF({conf})"

    # ---- macro direction filter (Strict) ----
    if direction == "LONG" and not allow_long:
        allowed = False
        reason = f"BLOCKED_BY_MACRO({bias})"
    if direction == "SHORT" and not allow_short:
        allowed = False
        reason = f"BLOCKED_BY_MACRO({bias})"

    # ---- context score ----
    context_score = round((conf * 0.7) + (bias_strength * 0.3), 2)

    # ❌ ถ้าไม่ผ่าน: คืน None ให้ wave_engine ตัดทิ้ง
    if not allowed:
        return None

    # ✅ ถ้าผ่าน: คืน “scenario เดิม” + แนบฟิลด์ debug
    out = dict(scenario)
    out["allowed"] = True
    out["gate_reason"] = reason
    out["context_score"] = context_score
    return out