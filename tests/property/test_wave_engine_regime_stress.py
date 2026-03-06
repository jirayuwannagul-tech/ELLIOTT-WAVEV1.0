from unittest.mock import patch

import pandas as pd
from hypothesis import given, strategies as st, settings

from app.analysis.wave_engine import analyze_symbol


def _make_df(prices):
    return pd.DataFrame({
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * len(prices),
    })


@settings(max_examples=15, deadline=None)
@given(
    prices=st.lists(
        st.floats(min_value=1, max_value=100000, allow_nan=False, allow_infinity=False),
        min_size=260,
        max_size=320,
    ),
    mode=st.sampled_from(["TREND", "SIDEWAY"]),
)
@patch("app.analysis.wave_engine.detect_market_mode")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.fetch_ohlcv")
def test_wave_engine_regime_no_crash(fetch_mock, drop_mock, mode_mock, prices, mode):
    df = _make_df(prices)

    fetch_mock.return_value = df
    drop_mock.return_value = df
    mode_mock.return_value = mode

    result = analyze_symbol("BTCUSDT")

    assert result is None or isinstance(result, dict)