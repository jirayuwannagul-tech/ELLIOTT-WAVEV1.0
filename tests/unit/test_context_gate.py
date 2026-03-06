from app.analysis.context_gate import apply_context_gate


def _scenario(direction="LONG", confidence=70.0):
    return {
        "direction": direction,
        "confidence": confidence,
    }


def _macro(bias="LONG", strength=60.0, allow_long=True, allow_short=True):
    return {
        "bias": bias,
        "strength": strength,
        "allow_long": allow_long,
        "allow_short": allow_short,
    }


class TestContextGate:
    def test_valid_long_passes(self):
        """LONG + macro LONG + conf สูงพอ → ผ่าน"""
        result = apply_context_gate(
            _scenario("LONG", 70.0),
            _macro("LONG", 60.0, allow_long=True, allow_short=False),
            min_confidence=65.0,
        )
        assert result is not None
        assert result["allowed"] is True

    def test_low_confidence_blocked(self):
        """confidence ต่ำกว่า threshold → ถูกบล็อก"""
        result = apply_context_gate(
            _scenario("LONG", 50.0),
            _macro("LONG", 60.0),
            min_confidence=65.0,
        )
        assert result is None

    def test_long_blocked_by_bear_macro(self):
        """LONG แต่ macro BEAR → ถูกบล็อก"""
        result = apply_context_gate(
            _scenario("LONG", 70.0),
            _macro("SHORT", 60.0, allow_long=False, allow_short=True),
            min_confidence=65.0,
        )
        assert result is None

    def test_short_blocked_by_bull_macro(self):
        """SHORT แต่ macro BULL → ถูกบล็อก"""
        result = apply_context_gate(
            _scenario("SHORT", 70.0),
            _macro("LONG", 60.0, allow_long=True, allow_short=False),
            min_confidence=65.0,
        )
        assert result is None

    def test_context_score_calculated(self):
        """ผ่านแล้วต้องมี context_score"""
        result = apply_context_gate(
            _scenario("LONG", 70.0),
            _macro("LONG", 60.0, allow_long=True, allow_short=False),
            min_confidence=65.0,
        )
        assert result is not None
        assert "context_score" in result
        assert result["context_score"] > 0

    def test_neutral_macro_allows_both(self):
        """macro NEUTRAL → ทั้ง LONG และ SHORT ผ่านได้"""
        for direction in ("LONG", "SHORT"):
            result = apply_context_gate(
                _scenario(direction, 70.0),
                _macro("NEUTRAL", 30.0, allow_long=True, allow_short=True),
                min_confidence=65.0,
            )
            assert result is not None, f"{direction} ควรผ่านใน NEUTRAL macro"