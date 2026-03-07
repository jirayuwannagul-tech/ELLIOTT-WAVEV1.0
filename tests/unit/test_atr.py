# tests/unit/test_atr.py
import pytest
import pandas as pd
import numpy as np
from app.indicators.atr import atr, add_atr


def _make_df(n=50, high=105.0, low=95.0, close=100.0):
    return pd.DataFrame({
        "high":  [high] * n,
        "low":   [low] * n,
        "close": [close] * n,
    })


class TestAtr:
    def test_returns_series(self):
        df = _make_df(50)
        result = atr(df)
        assert isinstance(result, pd.Series)

    def test_same_length_as_input(self):
        df = _make_df(50)
        result = atr(df)
        assert len(result) == 50

    def test_constant_candles_atr_equals_range(self):
        # high-low = 10 ตลอด, prev_close = close → tr = 10
        df = _make_df(50, high=110.0, low=100.0, close=105.0)
        result = atr(df, length=14)
        assert result.iloc[-1] == pytest.approx(10.0, rel=1e-3)

    def test_no_nan_at_end(self):
        df = _make_df(50)
        result = atr(df)
        assert not np.isnan(result.iloc[-1])

    def test_atr_positive(self):
        df = _make_df(50)
        result = atr(df)
        assert result.iloc[-1] > 0


class TestAddAtr:
    def test_default_column_added(self):
        df = _make_df(50)
        result = add_atr(df)
        assert "atr14" in result.columns

    def test_custom_length(self):
        df = _make_df(50)
        result = add_atr(df, length=7)
        assert "atr7" in result.columns

    def test_original_df_not_modified(self):
        df = _make_df(50)
        add_atr(df)
        assert "atr14" not in df.columns

    def test_returns_dataframe(self):
        df = _make_df(50)
        result = add_atr(df)
        assert isinstance(result, pd.DataFrame)

    def test_close_column_preserved(self):
        df = _make_df(50)
        result = add_atr(df)
        assert "close" in result.columns