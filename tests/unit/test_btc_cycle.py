# tests/unit/test_btc_cycle.py
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from app.analysis.btc_cycle import (
    _calc_atr, _find_weekly_pivots, _count_primary_waves,
    _get_current_wave, analyze_primary_wave, get_primary_bias,
)


def _make_df(n=50):
    closes = [100.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "open":  [c * 0.999 for c in closes],
        "high":  [c * 1.01  for c in closes],
        "low":   [c * 0.99  for c in closes],
        "close": closes,
        "volume": [1000.0] * n,
    })


def _make_pivots():
    return [
        {"index": 0,  "type": "L", "price": 100.0, "ts": None},
        {"index": 10, "type": "H", "price": 150.0, "ts": None},
        {"index": 20, "type": "L", "price": 120.0, "ts": None},
        {"index": 30, "type": "H", "price": 180.0, "ts": None},
        {"index": 40, "type": "L", "price": 140.0, "ts": None},
    ]


class TestCalcAtr:
    def test_returns_series(self):
        df = _make_df(50)
        result = _calc_atr(df)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        df = _make_df(50)
        assert len(_calc_atr(df)) == 50

    def test_positive_values(self):
        df = _make_df(50)
        result = _calc_atr(df).dropna()
        assert (result > 0).all()


class TestFindWeeklyPivots:
    def test_too_short_returns_empty(self):
        df = _make_df(10)
        assert _find_weekly_pivots(df) == []

    def test_none_returns_empty(self):
        assert _find_weekly_pivots(None) == []

    def test_returns_list(self):
        df = _make_df(50)
        result = _find_weekly_pivots(df)
        assert isinstance(result, list)

    def test_pivots_have_required_keys(self):
        df = _make_df(50)
        result = _find_weekly_pivots(df)
        for p in result:
            assert "type" in p
            assert "price" in p
            assert p["type"] in ("H", "L")

    def test_zigzag_alternates_hl(self):
        df = _make_df(50)
        result = _find_weekly_pivots(df)
        for i in range(1, len(result)):
            assert result[i]["type"] != result[i-1]["type"]


class TestCountPrimaryWaves:
    def test_too_few_pivots(self):
        assert _count_primary_waves([]) == []
        assert _count_primary_waves([{"price": 100}]) == []

    def test_returns_list(self):
        result = _count_primary_waves(_make_pivots())
        assert isinstance(result, list)

    def test_wave_count(self):
        pivots = _make_pivots()
        result = _count_primary_waves(pivots)
        assert len(result) == len(pivots) - 1

    def test_wave_has_required_keys(self):
        result = _count_primary_waves(_make_pivots())
        for w in result:
            for key in ["wave", "direction", "start", "end", "size", "pct"]:
                assert key in w

    def test_direction_up_down(self):
        result = _count_primary_waves(_make_pivots())
        for w in result:
            assert w["direction"] in ("UP", "DOWN")


class TestGetCurrentWave:
    def test_empty_waves_returns_empty(self):
        assert _get_current_wave([], 100.0) == {}

    def test_returns_required_keys(self):
        waves = _count_primary_waves(_make_pivots())
        result = _get_current_wave(waves, 150.0)
        for key in ["wave", "direction", "bias", "fib_targets", "retrace_pct"]:
            assert key in result

    def test_bull_bias(self):
        waves = [{"wave": "3", "direction": "UP",
                  "start": {"price": 100.0}, "end": {"price": 150.0},
                  "size": 50.0, "pct": 50.0}]
        result = _get_current_wave(waves, 140.0)
        assert result["bias"] == "BULLISH"

    def test_bear_bias(self):
        waves = [{"wave": "4", "direction": "DOWN",
                  "start": {"price": 150.0}, "end": {"price": 100.0},
                  "size": 50.0, "pct": 33.0}]
        result = _get_current_wave(waves, 120.0)
        assert result["bias"] == "BEARISH"


class TestAnalyzePrimaryWave:
    def test_empty_df_returns_empty(self):
        with patch("app.data.binance_fetcher.fetch_ohlcv", side_effect=Exception("no data")):
            result = analyze_primary_wave("BTCUSDT", None)
        assert result == {}

    def test_short_df_returns_empty(self):
        df = _make_df(10)
        assert analyze_primary_wave("BTCUSDT", df) == {}

    def test_valid_df_returns_dict(self):
        df = _make_df(50)
        with patch("app.analysis.btc_cycle._find_weekly_pivots", return_value=_make_pivots()):
            result = analyze_primary_wave("BTCUSDT", df)
        assert isinstance(result, dict)

    def test_symbol_in_result(self):
        df = _make_df(50)
        with patch("app.analysis.btc_cycle._find_weekly_pivots", return_value=_make_pivots()):
            result = analyze_primary_wave("ETHUSDT", df)
        if result:
            assert result["symbol"] == "ETHUSDT"


class TestGetPrimaryBias:
    def test_fallback_when_no_result(self):
        with patch("app.analysis.btc_cycle.analyze_primary_wave", return_value={}):
            result = get_primary_bias("BTCUSDT")
        assert result["bias"] == "NEUTRAL"
        assert result["direction"] == "UNKNOWN"

    def test_returns_required_keys(self):
        with patch("app.analysis.btc_cycle.analyze_primary_wave", return_value={}):
            result = get_primary_bias()
        for key in ["wave", "degree", "direction", "bias", "fib_targets"]:
            assert key in result

    def test_valid_result_passed_through(self):
        mock = {
            "wave": "3", "direction": "UP", "bias": "BULLISH",
            "note": "test", "fib_targets": {}, "wave_high": 200.0, "wave_low": 100.0,
        }
        with patch("app.analysis.btc_cycle.analyze_primary_wave", return_value=mock):
            result = get_primary_bias()
        assert result["bias"] == "BULLISH"
        assert result["direction"] == "UP"