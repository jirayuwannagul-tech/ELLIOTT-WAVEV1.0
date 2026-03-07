# tests/unit/test_rsi.py
import pytest
import pandas as pd
import numpy as np
from app.indicators.rsi import rsi, add_rsi


def _make_series(values):
    return pd.Series(values, dtype=float)


def _make_df(n=50, start=100.0):
    closes = [start + i for i in range(n)]
    return pd.DataFrame({"close": closes})


class TestRsi:
    def test_returns_series(self):
        s = _make_series(range(1, 51))
        result = rsi(s)
        assert isinstance(result, pd.Series)

    def test_same_length_as_input(self):
        s = _make_series(range(50))
        result = rsi(s)
        assert len(result) == 50

    def test_range_0_to_100(self):
        s = _make_series(range(1, 51))
        result = rsi(s)
        assert result.iloc[-1] >= 0
        assert result.iloc[-1] <= 100

    def test_uptrend_rsi_above_50(self):
        # ราคาขึ้นตลอด → RSI สูง
        s = _make_series([float(i) for i in range(1, 51)])
        result = rsi(s, length=14)
        assert result.iloc[-1] > 50

    def test_downtrend_rsi_below_50(self):
        # ราคาลงตลอด → RSI ต่ำ
        s = _make_series([float(50 - i) for i in range(50)])
        result = rsi(s, length=14)
        assert result.iloc[-1] < 50

    def test_constant_series_no_crash(self):
        s = _make_series([100.0] * 50)
        result = rsi(s)
        assert not np.isnan(result.iloc[-1])

    def test_no_nan_at_end(self):
        s = _make_series(range(50))
        result = rsi(s)
        assert not np.isnan(result.iloc[-1])


class TestAddRsi:
    def test_default_column_added(self):
        df = _make_df()
        result = add_rsi(df)
        assert "rsi14" in result.columns

    def test_custom_length(self):
        df = _make_df()
        result = add_rsi(df, length=7)
        assert "rsi7" in result.columns

    def test_original_df_not_modified(self):
        df = _make_df()
        add_rsi(df)
        assert "rsi14" not in df.columns

    def test_returns_dataframe(self):
        df = _make_df()
        result = add_rsi(df)
        assert isinstance(result, pd.DataFrame)

    def test_close_preserved(self):
        df = _make_df()
        result = add_rsi(df)
        assert "close" in result.columns