from hypothesis import given, strategies as st, settings

from app.analysis.macro_bias import compute_macro_bias


@settings(max_examples=30, deadline=None)
@given(
    regime_name=st.sampled_from(["TREND", "RANGE", "CHOP", "UNKNOWN"]),
    trend=st.sampled_from(["BULL", "BEAR", "NEUTRAL"]),
    vol=st.sampled_from(["LOW", "MID", "HIGH"]),
    trend_strength=st.floats(min_value=0, max_value=100),
    vol_score=st.floats(min_value=0, max_value=100),
    rsi14=st.floats(min_value=0, max_value=100),
)
def test_compute_macro_bias_no_crash(
    regime_name,
    trend,
    vol,
    trend_strength,
    vol_score,
    rsi14,
):
    regime = {
        "regime": regime_name,
        "trend": trend,
        "vol": vol,
        "trend_strength": trend_strength,
        "vol_score": vol_score,
    }

    result = compute_macro_bias(regime, rsi14=rsi14)

    assert isinstance(result, dict)
    assert result["bias"] in ["LONG", "SHORT", "NEUTRAL"]
    assert 0 <= result["strength"] <= 100
    assert isinstance(result["allow_long"], bool)
    assert isinstance(result["allow_short"], bool)