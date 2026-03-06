from hypothesis import given, strategies as st

from app.analysis.wave_rules import validate_abc


@given(
    a=st.floats(min_value=1, max_value=100000),
    b=st.floats(min_value=1, max_value=100000),
    c=st.floats(min_value=1, max_value=100000),
)
def test_abc_logic(a, b, c):

    pivots = [
        {"price": a, "type": "H"},
        {"price": b, "type": "L"},
        {"price": c, "type": "H"},
    ]

    ok, _ = validate_abc(pivots, "UP")

    assert isinstance(ok, bool)