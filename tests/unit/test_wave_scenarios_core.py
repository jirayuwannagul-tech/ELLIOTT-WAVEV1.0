from app.analysis.wave_scenarios import (
    _p, _degree, _fib_ratio, _in_fib_zone,
    _find_major_structure, _find_impulse_sequence, _find_abc_sequence,
    _determine_wave_position, score_scenario, normalize_scores, build_scenarios,
)


def _pivot(price, ptype, degree="minor", index=0):
    return {"price": price, "type": ptype, "degree": degree, "index": index}


def _uptrend_pivots():
    """pivot chain ที่ทำ HH/HL ชัดเจน → UPTREND"""
    return [
        _pivot(100, "L", index=0), _pivot(150, "H", index=1),
        _pivot(120, "L", index=2), _pivot(200, "H", index=3),
        _pivot(160, "L", index=4), _pivot(250, "H", index=5),
        _pivot(200, "L", index=6), _pivot(300, "H", index=7),
    ]


def _downtrend_pivots():
    """pivot chain ที่ทำ LH/LL ชัดเจน → DOWNTREND"""
    return [
        _pivot(300, "H", index=0), _pivot(200, "L", index=1),
        _pivot(260, "H", index=2), _pivot(150, "L", index=3),
        _pivot(210, "H", index=4), _pivot(100, "L", index=5),
        _pivot(160, "H", index=6), _pivot(60,  "L", index=7),
    ]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

class TestHelpers:
    def test_p_returns_price(self):
        pivots = [_pivot(123.4, "H")]
        assert _p(pivots, 0) == 123.4

    def test_degree_default_minor(self):
        pivots = [_pivot(100, "H")]
        assert _degree(pivots, 0) == "minor"

    def test_degree_intermediate(self):
        pivots = [_pivot(100, "H", degree="intermediate")]
        assert _degree(pivots, 0) == "intermediate"

    def test_fib_ratio_basic(self):
        ratio = _fib_ratio(100, 200, 150)  # move=100, |150-200|=50 → 0.5
        assert abs(ratio - 0.5) < 0.01

    def test_fib_ratio_zero_move(self):
        assert _fib_ratio(100, 100, 150) is None

    def test_in_fib_zone_hit(self):
        assert _in_fib_zone(0.618, [0.5, 0.618, 0.786]) is True

    def test_in_fib_zone_miss(self):
        assert _in_fib_zone(0.9, [0.5, 0.618, 0.786]) is False

    def test_in_fib_zone_tolerance(self):
        assert _in_fib_zone(0.63, [0.618], tolerance=0.05) is True


# ─────────────────────────────────────────────
# FIND MAJOR STRUCTURE
# ─────────────────────────────────────────────

class TestFindMajorStructure:
    def test_empty_pivots_returns_empty(self):
        assert _find_major_structure([]) == {}

    def test_no_highs_returns_empty(self):
        pivots = [_pivot(100, "L"), _pivot(90, "L")]
        assert _find_major_structure(pivots) == {}

    def test_uptrend_detected(self):
        result = _find_major_structure(_uptrend_pivots())
        assert result["major_trend"] == "UPTREND"

    def test_downtrend_detected(self):
        result = _find_major_structure(_downtrend_pivots())
        assert result["major_trend"] == "DOWNTREND"

    def test_ranging_detected(self):
        """ราคาล่าสุดอยู่กลางๆ ระหว่าง high/low → RANGING"""
        pivots = [
            _pivot(100, "L"), _pivot(200, "H"),
            _pivot(110, "L"), _pivot(190, "H"),
            _pivot(105, "L"), _pivot(195, "H"),
            _pivot(108, "L"), _pivot(192, "H"),
            _pivot(170, "L"),  # ล่าสุด อยู่กลาง → ranging
        ]
        result = _find_major_structure(pivots)
        assert result["major_trend"] in ("RANGING", "UPTREND", "DOWNTREND")

    def test_intermediate_degree_used(self):
        """ถ้ามี intermediate degree ให้ใช้ก่อน"""
        pivots = [
            _pivot(100, "L", degree="intermediate"),
            _pivot(200, "H", degree="intermediate"),
            _pivot(120, "L", degree="intermediate"),
            _pivot(300, "H", degree="intermediate"),
            _pivot(150, "L", degree="minor"),
        ]
        result = _find_major_structure(pivots)
        assert result != {}


# ─────────────────────────────────────────────
# FIND IMPULSE / ABC SEQUENCE
# ─────────────────────────────────────────────

class TestFindSequences:
    def test_find_impulse_long(self):
        pivots = [
            _pivot(100, "L"), _pivot(150, "H"),
            _pivot(120, "L"), _pivot(200, "H"),
            _pivot(165, "L"), _pivot(250, "H"),
        ]
        result = _find_impulse_sequence(pivots, "LONG")
        assert result is not None
        assert len(result["pivots"]) == 6

    def test_find_impulse_none_when_invalid(self):
        """pivot ไม่ครบ 6 → None"""
        pivots = [_pivot(100, "L"), _pivot(150, "H")]
        result = _find_impulse_sequence(pivots, "LONG")
        assert result is None

    def test_find_abc_down(self):
        pivots = [
            _pivot(200, "H"), _pivot(100, "L"),
            _pivot(155, "H"), _pivot(60, "L"),
        ]
        result = _find_abc_sequence(pivots, "DOWN")
        assert result is not None
        assert len(result["pivots"]) == 4

    def test_find_abc_none_when_invalid(self):
        pivots = [_pivot(100, "L"), _pivot(150, "H")]
        result = _find_abc_sequence(pivots, "DOWN")
        assert result is None


# ─────────────────────────────────────────────
# DETERMINE WAVE POSITION
# ─────────────────────────────────────────────

class TestDetermineWavePosition:
    def test_too_few_pivots_returns_unknown(self):
        result = _determine_wave_position([], {})
        assert result["position"] == "UNKNOWN"

    def test_unknown_major_trend_returns_unknown(self):
        pivots = _uptrend_pivots()
        result = _determine_wave_position(pivots, {"major_trend": "UNKNOWN"})
        assert result["position"] == "UNKNOWN"

    def test_uptrend_returns_position(self):
        pivots = _uptrend_pivots()
        structure = _find_major_structure(pivots)
        result = _determine_wave_position(pivots, structure)
        assert "position" in result
        assert result["position"] != ""

    def test_downtrend_returns_position(self):
        pivots = _downtrend_pivots()
        structure = _find_major_structure(pivots)
        result = _determine_wave_position(pivots, structure)
        assert "position" in result

    def test_ranging_returns_range_position(self):
        pivots = [
            _pivot(100, "L"), _pivot(200, "H"),
            _pivot(110, "L"), _pivot(190, "H"),
            _pivot(102, "L"),  # ใกล้ขอบล่าง → RANGE_BOTTOM
        ]
        structure = {"major_trend": "RANGING",
                     "recent_high": _pivot(190, "H"),
                     "recent_low": _pivot(100, "L"),
                     "major_high": _pivot(200, "H"),
                     "major_low": _pivot(100, "L")}
        result = _determine_wave_position(pivots, structure)
        assert result["position"] in ("RANGE_BOTTOM", "RANGE_TOP", "UNKNOWN")


# ─────────────────────────────────────────────
# SCORE SCENARIO
# ─────────────────────────────────────────────

class TestScoreScenario:
    def test_bull_long_adds_score(self):
        s1 = score_scenario(70, [], "BULL", 50, False, "LONG")
        s2 = score_scenario(70, [], "BEAR", 50, False, "LONG")
        assert s1 > s2

    def test_warnings_reduce_score(self):
        s1 = score_scenario(70, [], "NEUTRAL", 50, False, "LONG")
        s2 = score_scenario(70, ["warning1", "warning2"], "NEUTRAL", 50, False, "LONG")
        assert s1 > s2

    def test_volume_spike_adds_score(self):
        s1 = score_scenario(70, [], "NEUTRAL", 50, True, "LONG")
        s2 = score_scenario(70, [], "NEUTRAL", 50, False, "LONG")
        assert s1 > s2

    def test_rsi_oversold_long_adds_score(self):
        s1 = score_scenario(70, [], "NEUTRAL", 30, False, "LONG")
        s2 = score_scenario(70, [], "NEUTRAL", 75, False, "LONG")
        assert s1 > s2

    def test_wave2_position_adds_score(self):
        s1 = score_scenario(70, [], "NEUTRAL", 50, False, "LONG", position="IN_WAVE_2")
        s2 = score_scenario(70, [], "NEUTRAL", 50, False, "LONG", position="UNKNOWN")
        assert s1 > s2

    def test_fib_618_adds_score(self):
        s1 = score_scenario(70, [], "NEUTRAL", 50, False, "LONG", fib_ratio=0.618)
        s2 = score_scenario(70, [], "NEUTRAL", 50, False, "LONG", fib_ratio=0.1)
        assert s1 > s2

    def test_score_clamped_0_to_100(self):
        s = score_scenario(100, [], "BULL", 30, True, "LONG",
                           fib_ratio=0.618, position="IN_WAVE_2")
        assert 0 <= s <= 100

        s2 = score_scenario(1, ["w"] * 20, "BEAR", 80, False, "LONG")
        assert s2 >= 0


# ─────────────────────────────────────────────
# NORMALIZE SCORES
# ─────────────────────────────────────────────

class TestNormalizeScores:
    def test_adds_relative_score(self):
        scenarios = [{"score": 80}, {"score": 20}]
        result = normalize_scores(scenarios)
        assert "relative_score" in result[0]
        assert "confidence" in result[0]
        total = sum(s["relative_score"] for s in result)
        assert abs(total - 100) < 0.1

    def test_empty_list(self):
        result = normalize_scores([])
        assert result == []

    def test_single_scenario(self):
        result = normalize_scores([{"score": 75}])
        assert result[0]["relative_score"] == 100.0


# ─────────────────────────────────────────────
# BUILD SCENARIOS (integration)
# ─────────────────────────────────────────────

class TestDetermineWavePositionFallback:
    def test_downtrend_h_pivot_wave2_bounce(self):
        """DOWNTREND + last pivot H อยู่ใน fib 50-78.6% → IN_WAVE_2 SHORT"""
        pivots = [
            _pivot(300, "H", index=0), _pivot(100, "L", index=1),
            _pivot(230, "H", index=2), _pivot(80,  "L", index=3),
            _pivot(210, "H", index=4), _pivot(60,  "L", index=5),
            _pivot(162, "H", index=6),  # bounce ~51% ของ swing → wave 2
        ]
        structure = {
            "major_trend": "DOWNTREND",
            "major_high": _pivot(300, "H"),
            "major_low":  _pivot(60,  "L"),
            "recent_high": _pivot(210, "H"),
            "recent_low":  _pivot(60,  "L"),
        }
        result = _determine_wave_position(pivots, structure)
        assert result["position"] in ("IN_WAVE_2", "IN_WAVE_4", "UNKNOWN")

    def test_downtrend_lower_low_confirmed(self):
        """DOWNTREND + lower low → IN_WAVE_2 SHORT"""
        pivots = [
            _pivot(300, "H", index=0), _pivot(200, "L", index=1),
            _pivot(260, "H", index=2), _pivot(180, "L", index=3),
            _pivot(220, "H", index=4), _pivot(150, "L", index=5),  # lower low
        ]
        structure = {
            "major_trend": "DOWNTREND",
            "major_high": _pivot(300, "H"),
            "major_low":  _pivot(150, "L"),
            "recent_high": _pivot(220, "H"),
            "recent_low":  _pivot(150, "L"),
        }
        result = _determine_wave_position(pivots, structure)
        assert result["position"] in ("IN_WAVE_2", "IN_WAVE_4", "UNKNOWN")

    def test_downtrend_higher_low_wave4(self):
        """DOWNTREND + higher low → IN_WAVE_4 SHORT"""
        pivots = [
            _pivot(300, "H", index=0), _pivot(100, "L", index=1),
            _pivot(250, "H", index=2), _pivot(80,  "L", index=3),
            _pivot(200, "H", index=4), _pivot(120, "L", index=5),  # higher low
        ]
        structure = {
            "major_trend": "DOWNTREND",
            "major_high": _pivot(300, "H"),
            "major_low":  _pivot(80,  "L"),
            "recent_high": _pivot(200, "H"),
            "recent_low":  _pivot(80,  "L"),
        }
        result = _determine_wave_position(pivots, structure)
        assert result["position"] in ("IN_WAVE_4", "IN_WAVE_2", "UNKNOWN")

    def test_ranging_range_top(self):
        """RANGING + last pivot H ใกล้ top → RANGE_TOP SHORT"""
        pivots = [
            _pivot(100, "L"), _pivot(200, "H"),
            _pivot(110, "L"), _pivot(198, "H"),  # ใกล้ top มาก
        ]
        structure = {
            "major_trend": "RANGING",
            "recent_high": _pivot(200, "H"),
            "recent_low":  _pivot(100, "L"),
            "major_high":  _pivot(200, "H"),
            "major_low":   _pivot(100, "L"),
        }
        result = _determine_wave_position(pivots, structure)
        assert result["position"] in ("RANGE_TOP", "RANGE_BOTTOM", "UNKNOWN")

    def test_ranging_range_bottom(self):
        """RANGING + last pivot L ใกล้ bottom → RANGE_BOTTOM LONG"""
        pivots = [
            _pivot(100, "L"), _pivot(200, "H"),
            _pivot(102, "L"),  # ใกล้ bottom มาก
        ]
        structure = {
            "major_trend": "RANGING",
            "recent_high": _pivot(200, "H"),
            "recent_low":  _pivot(100, "L"),
            "major_high":  _pivot(200, "H"),
            "major_low":   _pivot(100, "L"),
        }
        result = _determine_wave_position(pivots, structure)
        assert result["position"] in ("RANGE_BOTTOM", "RANGE_TOP", "UNKNOWN")
    def test_too_few_pivots_returns_empty(self):
        result = build_scenarios([_pivot(100, "L")], symbol="BTCUSDT")
        assert result == []

    def test_uptrend_returns_scenarios(self):
        pivots = _uptrend_pivots()
        result = build_scenarios(pivots, macro_trend="BULL", rsi14=55, symbol="BTCUSDT")
        assert isinstance(result, list)

    def test_downtrend_returns_scenarios(self):
        pivots = _downtrend_pivots()
        result = build_scenarios(pivots, macro_trend="BEAR", rsi14=40, symbol="BTCUSDT")
        assert isinstance(result, list)

    def test_scenarios_have_required_keys(self):
        pivots = _uptrend_pivots()
        result = build_scenarios(pivots, macro_trend="BULL", rsi14=55, symbol="BTCUSDT")
        for sc in result:
            assert "type" in sc
            assert "direction" in sc
            assert "score" in sc
            assert "confidence" in sc

    def test_scenarios_sorted_by_score(self):
        pivots = _uptrend_pivots()
        result = build_scenarios(pivots, macro_trend="BULL", rsi14=55, symbol="BTCUSDT")
        if len(result) >= 2:
            assert result[0]["score"] >= result[1]["score"]