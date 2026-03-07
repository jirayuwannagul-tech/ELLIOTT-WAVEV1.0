# tests/unit/test_ema.py
import pytest
import pandas as pd
import numpy as np
from app.indicators.ema import ema, add_ema


def _make_series(values):
    return pd.Series(values, dtype=float)


def _make_df(n=50, start=100.0):
    closes = [start + i for i in range(n)]
    return pd.DataFrame({"close": closes})


class TestEma:
    def test_returns_series(self):
        s = _make_series([1, 2, 3, 4, 5])
        result = ema(s, length=3)
        assert isinstance(result, pd.Series)

    def test_same_length_as_input(self):
        s = _make_series(range(20))
        result = ema(s, length=5)
        assert len(result) == 20

    def test_constant_series_returns_same(self):
        s = _make_series([100.0] * 50)
        result = ema(s, length=10)
        assert result.iloc[-1] == pytest.approx(100.0)

    def test_uptrend_ema_below_last_price(self):
        s = _make_series([float(i) for i in range(1, 51)])
        result = ema(s, length=10)
        assert result.iloc[-1] < s.iloc[-1]

    def test_no_nan_at_end(self):
        s = _make_series(range(50))
        result = ema(s, length=10)
        assert not np.isnan(result.iloc[-1])


class TestAddEma:
    def test_default_lengths(self):
        df = _make_df(50)
        result = add_ema(df)
        assert "ema50" in result.columns
        assert "ema200" in result.columns

    def test_custom_lengths(self):
        df = _make_df(50)
        result = add_ema(df, lengths=(12, 26))
        assert "ema12" in result.columns
        assert "ema26" in result.columns

    def test_original_df_not_modified(self):
        df = _make_df(50)
        add_ema(df, lengths=(10,))
        assert "ema10" not in df.columns

    def test_returns_dataframe(self):
        df = _make_df(50)
        result = add_ema(df)
        assert isinstance(result, pd.DataFrame)

    def test_close_column_preserved(self):
        df = _make_df(50)
        result = add_ema(df)
        assert "close" in result.columns