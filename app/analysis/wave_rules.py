from typing import Dict, List, Tuple
from app.analysis.fib import fib_retracement, fib_extension, fib_zone_match


def _is_alternating_types(points: List[Dict]) -> bool:
    """Ensure pivot types alternate L/H/L/H... or H/L/H/L..."""
    if len(points) < 2:
        return False
    for i in range(1, len(points)):
        if points[i]["type"] == points[i - 1]["type"]:
            return False
    return True


def _price(points: List[Dict], i: int) -> float:
    return float(points[i]["price"])


def validate_impulse(points: List[Dict], direction: str) -> Tuple[bool, List[str]]:
    """
    Validate Elliott Impulse 1-5 using 6 pivots (0..5) representing:
    LONG  : L0-H1-L2-H3-L4-H5
    SHORT : H0-L1-H2-L3-H4-L5

    direction: "LONG" or "SHORT"
    Returns (pass, reasons)
    """
    reasons: List[str] = []
    direction = (direction or "").upper().strip()

    if len(points) != 6:
        return False, ["Impulse ต้องใช้ pivot 6 จุด (0..5)"]

    if not _is_alternating_types(points):
        return False, ["ชนิด pivot ไม่สลับ H/L ต่อเนื่อง"]

    # Assign pivots
    p0, p1, p2, p3, p4, p5 = points

    if direction == "LONG":
        expected = ["L", "H", "L", "H", "L", "H"]
    elif direction == "SHORT":
        expected = ["H", "L", "H", "L", "H", "L"]
    else:
        return False, ["direction ต้องเป็น LONG หรือ SHORT"]

    if [p["type"] for p in points] != expected:
        return False, [f"Impulse {direction} ต้องเป็น pattern {''.join(expected)}"]

    # Rule 1: Wave 2 must not retrace beyond start of Wave 1
    # LONG: p2 must be above p0
    # SHORT: p2 must be below p0
    if direction == "LONG":
        if _price(points, 2) <= _price(points, 0):
            reasons.append("ผิดกฎ: Wave2 หลุดจุดเริ่ม Wave1 (invalid)")
    else:
        if _price(points, 2) >= _price(points, 0):
            reasons.append("ผิดกฎ: Wave2 หลุดจุดเริ่ม Wave1 (invalid)")

    # Rule 2: Wave 3 must not be the shortest among 1,3,5
    # Measure wave lengths by absolute price move
    w1 = abs(_price(points, 1) - _price(points, 0))
    w3 = abs(_price(points, 3) - _price(points, 2))
    w5 = abs(_price(points, 5) - _price(points, 4))

    if w3 <= min(w1, w5):
        reasons.append("ผิดกฎ: Wave3 สั้นสุด (invalid)")

    # Rule 3: Wave 4 must not overlap Wave 1 (classic impulse)
    # LONG: wave4 low (p4) must be above wave1 high (p1)
    # SHORT: wave4 high (p4) must be below wave1 low (p1)
    if direction == "LONG":
        if _price(points, 4) <= _price(points, 1):
            reasons.append("ผิดกฎ: Wave4 overlap Wave1 (invalid)")
    else:
        if _price(points, 4) >= _price(points, 1):
            reasons.append("ผิดกฎ: Wave4 overlap Wave1 (invalid)")

    # ---- Fibonacci validation ----
    # Wave2 retracement (ต้องกันหารศูนย์)
    if direction == "LONG":
        wave1_len = _price(points, 1) - _price(points, 0)
    else:
        wave1_len = _price(points, 0) - _price(points, 1)

    if wave1_len == 0:
        reasons.append("Wave1 length = 0 (คำนวณ Fib ไม่ได้)")
    else:
        wave2_retrace = fib_retracement(_price(points, 0), _price(points, 1), _price(points, 2))
        if wave2_retrace is None or not fib_zone_match(wave2_retrace):
            reasons.append("Wave2 retrace ไม่อยู่ในช่วง 0.382–0.786")

        # Wave3 extension
        wave3_targets = fib_extension(_price(points, 0), _price(points, 1), _price(points, 2))
        wave3_ext = w3 / abs(wave1_len)
        if wave3_ext < 1.0:
            reasons.append("Wave3 extension < 1.0 (อ่อนเกิน)")

    ok = len(reasons) == 0
    return ok, reasons


def validate_abc(points: List[Dict], direction: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    direction = (direction or "").upper().strip()

    if len(points) != 4:
        return False, ["ABC ต้องใช้ pivot 4 จุด (0..3)"]

    if not _is_alternating_types(points):
        return False, ["ชนิด pivot ไม่สลับ H/L ต่อเนื่อง"]

    p0, p1, p2, p3 = points

    if direction == "DOWN":
        expected = ["H", "L", "H", "L"]
        if [p["type"] for p in points] != expected:
            return False, [f"ABC DOWN ต้องเป็น pattern {''.join(expected)}"]

        # ✅ HARD block: C ต้องทำ low ต่ำกว่า A
        if _price(points, 3) >= _price(points, 1):
            return False, ["C ไม่ทำ low ต่ำกว่า A (invalid)"]

    elif direction == "UP":
        expected = ["L", "H", "L", "H"]
        if [p["type"] for p in points] != expected:
            return False, [f"ABC UP ต้องเป็น pattern {''.join(expected)}"]

        # ✅ HARD block: C ต้องทำ high สูงกว่า A
        if _price(points, 3) <= _price(points, 1):
            return False, ["C ไม่ทำ high สูงกว่า A (invalid)"]

    else:
        return False, ["direction ต้องเป็น UP หรือ DOWN"]

    a_len = abs(_price(points, 1) - _price(points, 0))
    if a_len == 0:
        reasons.append("Wave A length = 0 (คำนวณ Fib ไม่ได้)")
        return True, reasons

    b_retrace = abs((_price(points, 2) - _price(points, 1)) / a_len)

    if 0.382 <= b_retrace <= 0.618:
        reasons.append("ABC: คล้าย Zigzag (B retrace 0.382–0.618)")
    elif b_retrace >= 0.8:
        reasons.append("ABC: คล้าย Flat (B retrace >= 0.8)")
    else:
        # ✅ HARD block: B retrace ไม่อยู่ใน zone ที่รู้จัก
        return False, ["ABC: B retrace ไม่ชัด — ไม่ใช่ Zigzag หรือ Flat"]

    c_len = abs(_price(points, 3) - _price(points, 2))
    c_ext = c_len / a_len
    if c_ext < 1.0:
        reasons.append("ABC: Wave C สั้นกว่า A (อ่อน)")
    elif c_ext >= 1.618:
        reasons.append("ABC: Wave C ยืดแรง (>=1.618)")

    return True, reasons