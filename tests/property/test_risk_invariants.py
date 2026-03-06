from hypothesis import given, strategies as st

from app.risk.risk_manager import calculate_rr


@given(
    entry=st.floats(min_value=1, max_value=100000),
    sl=st.floats(min_value=1, max_value=100000),
    tp=st.floats(min_value=1, max_value=100000),
)
def test_rr_invariant(entry, sl, tp):

    rr = calculate_rr(entry, sl, tp)

    assert rr >= 0