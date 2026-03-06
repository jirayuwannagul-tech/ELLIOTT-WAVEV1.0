from hypothesis import given, strategies as st, settings
from unittest.mock import patch
import pandas as pd

from app.analysis.wave_engine import analyze_symbol


@settings(max_examples=20, deadline=None)
@given(
    prices=st.lists(
        st.floats(min_value=1, max_value=100000),
        min_size=200,
        max_size=400
    )
)
@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
def test_wave_engine_no_crash(drop, fetch, prices):

    df = pd.DataFrame({
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000]*len(prices)
    })

    fetch.return_value = df
    drop.return_value = df

    result = analyze_symbol("BTCUSDT")

    assert result is None or isinstance(result, dict)