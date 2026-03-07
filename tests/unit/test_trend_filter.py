# tests/unit/test_trend_filter.py
import pytest
import pandas as pd
from app.indicators.trend_filter import trend_filter_ema, allow_direction


def _make_df(close, ema50, ema200):
    return pd.DataFrame({
        "close":  [close],
        "ema50":  [ema50],
        "ema200": [ema200],
    })


class TestTrendFilterEma:
    def test_bull(self):
        df = _make_df(close=120.0, ema50=110.0, ema200=100.0)
        assert trend_filter_ema(df) == "BULL"

    def test_bear(self):
        df = _make_df(close=80.0, ema50=90.0, ema200=100.0)
        assert trend_filter_ema(df) == "BEAR"

    def test_neutral_mixed(self):
        df = _make_df(close=105.0, ema50=110.0, ema200=100.0)
        assert trend_filter_ema(df) == "NEUTRAL"

    def test_missing_columns_returns_neutral(self):
        df = pd.DataFrame({"close": [100.0]})
        assert trend_filter_ema(df) == "NEUTRAL"

    def test_nan_ema_returns_neutral(self):
        import numpy as np
        df = _make_df(close=100.0, ema50=float("nan"), ema200=100.0)
        assert trend_filter_ema(df) == "NEUTRAL"

    def test_returns_string(self):
        df = _make_df(close=100.0, ema50=100.0, ema200=100.0)
        assert isinstance(trend_filter_ema(df), str)


class TestAllowDirection:
    def test_bull_allows_long(self):
        assert allow_direction("BULL", "LONG") is True

    def test_bull_blocks_short(self):
        assert allow_direction("BULL", "SHORT") is False

    def test_bear_allows_short(self):
        assert allow_direction("BEAR", "SHORT") is True

    def test_bear_blocks_long(self):
        assert allow_direction("BEAR", "LONG") is False

    def test_neutral_allows_both(self):
        assert allow_direction("NEUTRAL", "LONG") is True
        assert allow_direction("NEUTRAL", "SHORT") is True

    def test_empty_string_allows_both(self):
        assert allow_direction("", "LONG") is True