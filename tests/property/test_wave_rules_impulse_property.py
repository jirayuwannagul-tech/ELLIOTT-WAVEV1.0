from hypothesis import given, strategies as st, settings

from app.analysis.wave_rules import validate_impulse


@settings(max_examples=30, deadline=None)
@given(
    prices=st.lists(
        st.floats(min_value=1, max_value=100000, allow_nan=False, allow_infinity=False),
        min_size=6,
        max_size=6,
    )
)
def test_validate_impulse_no_crash_long(prices):
    pivots = [
        {"price": prices[0], "type": "L"},
        {"price": prices[1], "type": "H"},
        {"price": prices[2], "type": "L"},
        {"price": prices[3], "type": "H"},
        {"price": prices[4], "type": "L"},
        {"price": prices[5], "type": "H"},
    ]

    ok, reasons = validate_impulse(pivots, "LONG")

    assert isinstance(ok, bool)
    assert isinstance(reasons, list)


@settings(max_examples=30, deadline=None)
@given(
    prices=st.lists(
        st.floats(min_value=1, max_value=100000, allow_nan=False, allow_infinity=False),
        min_size=6,
        max_size=6,
    )
)
def test_validate_impulse_no_crash_short(prices):
    pivots = [
        {"price": prices[0], "type": "H"},
        {"price": prices[1], "type": "L"},
        {"price": prices[2], "type": "H"},
        {"price": prices[3], "type": "L"},
        {"price": prices[4], "type": "H"},
        {"price": prices[5], "type": "L"},
    ]

    ok, reasons = validate_impulse(pivots, "SHORT")

    assert isinstance(ok, bool)
    assert isinstance(reasons, list)