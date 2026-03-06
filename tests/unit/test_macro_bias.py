from app.analysis.macro_bias import compute_macro_bias


def _regime(regime="TREND", trend="BULL", vol="MID",
            trend_strength=50.0, vol_score=55.0):
    return {
        "regime": regime,
        "trend": trend,
        "vol": vol,
        "trend_strength": trend_strength,
        "vol_score": vol_score,
    }


class TestMacroBiasTrend:
    def test_trend_bull_returns_long(self):
        """TREND + BULL → bias=LONG"""
        result = compute_macro_bias(_regime("TREND", "BULL"), rsi14=60.0)
        assert result["bias"] == "LONG"
        assert result["allow_long"] is True
        assert result["allow_short"] is False

    def test_trend_bear_returns_short(self):
        """TREND + BEAR → bias=SHORT"""
        result = compute_macro_bias(_regime("TREND", "BEAR"), rsi14=40.0)
        assert result["bias"] == "SHORT"
        assert result["allow_short"] is True
        assert result["allow_long"] is False

    def test_trend_neutral_returns_neutral(self):
        """TREND + NEUTRAL → bias=NEUTRAL"""
        result = compute_macro_bias(_regime("TREND", "NEUTRAL"), rsi14=50.0)
        assert result["bias"] == "NEUTRAL"

    def test_bull_rsi_above_55_adds_strength(self):
        """BULL + RSI >= 55 → strength สูงกว่า"""
        r1 = compute_macro_bias(_regime("TREND", "BULL"), rsi14=60.0)
        r2 = compute_macro_bias(_regime("TREND", "BULL"), rsi14=40.0)
        assert r1["strength"] > r2["strength"]

    def test_bear_rsi_below_45_adds_strength(self):
        """BEAR + RSI <= 45 → strength สูงกว่า"""
        r1 = compute_macro_bias(_regime("TREND", "BEAR"), rsi14=40.0)
        r2 = compute_macro_bias(_regime("TREND", "BEAR"), rsi14=60.0)
        assert r1["strength"] > r2["strength"]


class TestMacroBiasRange:
    def test_range_neutral_default(self):
        """RANGE → bias=NEUTRAL ถ้า RSI กลางๆ"""
        result = compute_macro_bias(_regime("RANGE", "NEUTRAL"), rsi14=50.0)
        assert result["bias"] == "NEUTRAL"

    def test_range_rsi_high_leans_long(self):
        """RANGE + RSI >= 60 → bias=LONG เบาๆ"""
        result = compute_macro_bias(_regime("RANGE", "NEUTRAL"), rsi14=65.0)
        assert result["bias"] == "LONG"

    def test_range_rsi_low_leans_short(self):
        """RANGE + RSI <= 40 → bias=SHORT เบาๆ"""
        result = compute_macro_bias(_regime("RANGE", "NEUTRAL"), rsi14=35.0)
        assert result["bias"] == "SHORT"


class TestMacroBiasChop:
    def test_chop_always_neutral(self):
        """CHOP → bias=NEUTRAL เสมอ"""
        result = compute_macro_bias(_regime("CHOP", "NEUTRAL"), rsi14=50.0)
        assert result["bias"] == "NEUTRAL"
        assert result["allow_long"] is True
        assert result["allow_short"] is True

    def test_chop_high_vol_reduces_strength(self):
        """CHOP + HIGH vol → strength ต่ำกว่า MID vol"""
        r1 = compute_macro_bias(_regime("CHOP", vol="HIGH", vol_score=80.0), rsi14=50.0)
        r2 = compute_macro_bias(_regime("CHOP", vol="MID",  vol_score=55.0), rsi14=50.0)
        assert r1["strength"] < r2["strength"]


class TestMacroBiasVolPenalty:
    def test_high_vol_score_reduces_strength(self):
        """vol_score >= 75 → strength ลด 8"""
        r1 = compute_macro_bias(_regime("TREND", "BULL", vol_score=80.0), rsi14=50.0)
        r2 = compute_macro_bias(_regime("TREND", "BULL", vol_score=30.0), rsi14=50.0)
        assert r1["strength"] < r2["strength"]

    def test_strength_always_between_0_and_100(self):
        """strength ต้องอยู่ใน 0-100 เสมอ"""
        for rsi in (10.0, 50.0, 90.0):
            for regime in ("TREND", "RANGE", "CHOP"):
                result = compute_macro_bias(
                    _regime(regime, vol_score=90.0), rsi14=rsi
                )
                assert 0 <= result["strength"] <= 100

    def test_none_regime_returns_neutral(self):
        """regime=None → fallback NEUTRAL"""
        result = compute_macro_bias(None, rsi14=50.0)  # type: ignore[arg-type]
        assert result["bias"] == "NEUTRAL"