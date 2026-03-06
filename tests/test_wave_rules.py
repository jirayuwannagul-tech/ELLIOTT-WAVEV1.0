from app.analysis.wave_rules import validate_impulse, validate_abc


def _p(price, ptype):
    return {"price": price, "type": ptype}


# ─────────────────────────────────────────────
# IMPULSE LONG
# ─────────────────────────────────────────────

class TestImpulseLong:
    def test_valid_impulse(self):
        """impulse ที่ถูกต้องทุกกฎ"""
        points = [
            _p(100, "L"), _p(150, "H"),  # w1 = 50
            _p(120, "L"), _p(200, "H"),  # w3 = 80 (ยาวสุด)
            _p(160, "L"), _p(240, "H"),  # w5 = 80
        ]
        ok, reasons = validate_impulse(points, "LONG")
        assert ok is True, f"ควรผ่านแต่ไม่ผ่าน: {reasons}"

    def test_wave2_breaks_wave1_start(self):
        """wave2 ต่ำกว่าจุดเริ่ม wave1 → invalid"""
        points = [
            _p(100, "L"), _p(150, "H"),
            _p(90,  "L"),  # ❌ ต่ำกว่า 100
            _p(200, "H"),
            _p(160, "L"), _p(240, "H"),
        ]
        ok, reasons = validate_impulse(points, "LONG")
        assert ok is False
        assert any("Wave2" in r for r in reasons)

    def test_wave3_shortest_rejected(self):
        """wave3 สั้นที่สุด → invalid"""
        points = [
            _p(100, "L"), _p(200, "H"),  # w1 = 100
            _p(150, "L"), _p(170, "H"),  # w3 = 20 ❌ สั้นสุด
            _p(160, "L"), _p(400, "H"),  # w5 = 240
        ]
        ok, reasons = validate_impulse(points, "LONG")
        assert ok is False
        assert any("Wave3" in r for r in reasons)

    def test_wave4_overlaps_wave1(self):
        """wave4 ต่ำกว่า top ของ wave1 → invalid"""
        points = [
            _p(100, "L"), _p(150, "H"),  # w1 top = 150
            _p(120, "L"), _p(200, "H"),
            _p(140, "L"), _p(240, "H"),  # w4 low = 140 < 150 ❌
        ]
        ok, reasons = validate_impulse(points, "LONG")
        assert ok is False
        assert any("Wave4" in r for r in reasons)

    def test_wrong_pivot_pattern(self):
        """pattern ไม่ใช่ L-H-L-H-L-H → invalid"""
        points = [
            _p(100, "H"), _p(150, "L"),  # ❌ เริ่มด้วย H
            _p(120, "H"), _p(200, "L"),
            _p(160, "H"), _p(240, "L"),
        ]
        ok, reasons = validate_impulse(points, "LONG")
        assert ok is False

    def test_wrong_pivot_count(self):
        """ส่ง pivot มาไม่ครบ 6 จุด → invalid"""
        points = [
            _p(100, "L"), _p(150, "H"),
            _p(120, "L"), _p(200, "H"),
        ]
        ok, reasons = validate_impulse(points, "LONG")
        assert ok is False


# ─────────────────────────────────────────────
# IMPULSE SHORT
# ─────────────────────────────────────────────

class TestImpulseShort:
    def test_valid_impulse_short(self):
        """impulse short ที่ถูกต้อง"""
        points = [
            _p(240, "H"), _p(160, "L"),  # w1 = 80
            _p(200, "H"), _p(100, "L"),  # w3 = 100 (ยาวสุด)
            _p(140, "H"), _p(60,  "L"),  # w5 = 80
        ]
        ok, reasons = validate_impulse(points, "SHORT")
        assert ok is True, f"ควรผ่านแต่ไม่ผ่าน: {reasons}"

    def test_wave2_breaks_wave1_start_short(self):
        """wave2 สูงกว่าจุดเริ่ม wave1 → invalid"""
        points = [
            _p(240, "H"), _p(160, "L"),
            _p(250, "H"),  # ❌ สูงกว่า 240
            _p(100, "L"),
            _p(140, "H"), _p(60, "L"),
        ]
        ok, reasons = validate_impulse(points, "SHORT")
        assert ok is False
        assert any("Wave2" in r for r in reasons)


# ─────────────────────────────────────────────
# ABC
# ─────────────────────────────────────────────

class TestABCDown:
    def test_valid_zigzag_down(self):
        """ABC down zigzag ที่ถูกต้อง"""
        points = [
            _p(200, "H"), _p(100, "L"),  # A = 100
            _p(155, "H"), _p(50,  "L"),  # B retrace 55% | C < A ✅
        ]
        ok, reasons = validate_abc(points, "DOWN")
        assert ok is True, f"ควรผ่านแต่ไม่ผ่าน: {reasons}"

    def test_c_not_lower_than_a(self):
        """C ไม่ต่ำกว่า A → invalid (hard block)"""
        points = [
            _p(200, "H"), _p(100, "L"),
            _p(155, "H"), _p(110, "L"),  # C = 110 > A = 100 ❌
        ]
        ok, reasons = validate_abc(points, "DOWN")
        assert ok is False
        assert any("C" in r for r in reasons)

    def test_b_retrace_too_small(self):
        """B retrace น้อยเกินไป → ไม่ใช่ zigzag หรือ flat → invalid"""
        points = [
            _p(200, "H"), _p(100, "L"),  # A = 100
            _p(120, "H"), _p(50,  "L"),  # B retrace แค่ 20% ❌
        ]
        ok, reasons = validate_abc(points, "DOWN")
        assert ok is False


class TestABCUp:
    def test_valid_zigzag_up(self):
        """ABC up zigzag ที่ถูกต้อง"""
        points = [
            _p(100, "L"), _p(200, "H"),  # A = 100
            _p(145, "L"), _p(250, "H"),  # B retrace 55% | C > A ✅
        ]
        ok, reasons = validate_abc(points, "UP")
        assert ok is True, f"ควรผ่านแต่ไม่ผ่าน: {reasons}"

    def test_c_not_higher_than_a(self):
        """C ไม่สูงกว่า A → invalid (hard block)"""
        points = [
            _p(100, "L"), _p(200, "H"),
            _p(145, "L"), _p(190, "H"),  # C = 190 < A = 200 ❌
        ]
        ok, reasons = validate_abc(points, "UP")
        assert ok is False
        assert any("C" in r for r in reasons)

    def test_wrong_pivot_count(self):
        """ส่ง pivot มาไม่ครบ 4 จุด → invalid"""
        points = [
            _p(100, "L"), _p(200, "H"),
            _p(145, "L"),
        ]
        ok, reasons = validate_abc(points, "UP")
        assert ok is False