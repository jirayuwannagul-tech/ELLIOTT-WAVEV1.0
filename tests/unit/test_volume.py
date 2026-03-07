# tests/unit/test_volume.py
import pytest
import pandas as pd
import numpy as np
from app.indicators.volume import add_volume_ma, volume_spike


def _make_df(n=30, vol=1000.0):
    return pd.DataFrame({
        "close":  [100.0] * n,
        "volume": [vol] * n,
    })


class TestAddVolumeMa:
    def test_default_column_added(self):
        df = _make_df(30)
        result = add_volume_ma(df)
        assert "vol_ma20" in result.columns

    def test_custom_length(self):
        df = _make_df(30)
        result = add_volume_ma(df, length=10)
        assert "vol_ma10" in result.columns

    def test_original_not_modified(self):
        df = _make_df(30)
        add_volume_ma(df)
        assert "vol_ma20" not in df.columns

    def test_returns_dataframe(self):
        df = _make_df(30)
        assert isinstance(add_volume_ma(df), pd.DataFrame)

    def test_constant_volume_ma_equals_volume(self):
        df = _make_df(30, vol=500.0)
        result = add_volume_ma(df, length=10)
        assert result["vol_ma10"].iloc[-1] == pytest.approx(500.0)


class TestVolumeSpike:
    def test_spike_detected(self):
        df = _make_df(30, vol=1000.0)
        df = add_volume_ma(df, length=20)
        df.loc[df.index[-1], "volume"] = 2000.0
        assert volume_spike(df, length=20, multiplier=1.5) == True

    def test_no_spike(self):
        df = _make_df(30, vol=1000.0)
        df = add_volume_ma(df, length=20)
        assert volume_spike(df, length=20, multiplier=1.5) == False

    def test_nan_vol_ma_returns_false(self):
        df = _make_df(30)
        df = add_volume_ma(df, length=20)
        df.loc[df.index[-1], "vol_ma20"] = float("nan")
        assert volume_spike(df, length=20) == False