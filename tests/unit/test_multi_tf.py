# tests/unit/test_multi_tf.py
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np


def _make_df(n=300, trend="up"):
    closes = [100.0 + i * (0.5 if trend == "up" else -0.5) for i in range(n)]
    df = pd.DataFrame({
        "open":   [c * 0.999 for c in closes],
        "high":   [c * 1.002 for c in closes],
        "low":    [c * 0.998 for c in closes],
        "close":  closes,
        "volume": [1000.0] * n,
    })
    df["ema50"]  = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()
    df["rsi14"]  = 50.0
    df["atr14"]  = 1.0
    return df


def _make_pivots(last_h=110.0, last_l=90.0, n=10):
    pivots = []
    for i in range(n):
        pivots.append({"type": "H", "price": last_h - i, "idx": n - i})
        pivots.append({"type": "L", "price": last_l + i, "idx": n - i - 1})
    return pivots


class TestLastClose:
    def test_returns_float(self):
        from app.analysis.multi_tf import _last_close
        df = _make_df(10)
        assert isinstance(_last_close(df), float)

    def test_empty_returns_none(self):
        from app.analysis.multi_tf import _last_close
        assert _last_close(pd.DataFrame()) is None


class TestH4StructureConfirm:
    def test_too_short_returns_false(self):
        from app.analysis.multi_tf import _h4_structure_confirm
        df = _make_df(100)
        cl, cs, note = _h4_structure_confirm(df)
        assert cl is False
        assert cs is False
        assert "len<250" in note

    def test_none_returns_false(self):
        from app.analysis.multi_tf import _h4_structure_confirm
        cl, cs, note = _h4_structure_confirm(None)
        assert cl is False and cs is False

    def test_confirm_long_when_above_last_high(self):
        from app.analysis.multi_tf import _h4_structure_confirm
        df = _make_df(300, trend="up")
        # close สุดท้าย = ~249.5 lastH=110 → confirm_long=True
        with patch("app.analysis.multi_tf.find_fractal_pivots", return_value=_make_pivots(110.0, 90.0)), \
             patch("app.analysis.multi_tf.filter_pivots", side_effect=lambda x, **kw: x):
            cl, cs, note = _h4_structure_confirm(df)
        assert cl is True
        assert cs is False

    def test_confirm_short_when_below_last_low(self):
        from app.analysis.multi_tf import _h4_structure_confirm
        df = _make_df(300, trend="down")
        # close สุดท้าย = ~-49.5 ต่ำกว่า lastL=90 → confirm_short=True
        with patch("app.analysis.multi_tf.find_fractal_pivots", return_value=_make_pivots(200.0, 300.0)), \
             patch("app.analysis.multi_tf.filter_pivots", side_effect=lambda x, **kw: x):
            cl, cs, note = _h4_structure_confirm(df)
        assert cs is True
        assert cl is False

    def test_no_pivots_returns_false(self):
        from app.analysis.multi_tf import _h4_structure_confirm
        df = _make_df(300)
        with patch("app.analysis.multi_tf.find_fractal_pivots", return_value=[]), \
             patch("app.analysis.multi_tf.filter_pivots", return_value=[]):
            cl, cs, note = _h4_structure_confirm(df)
        assert cl is False and cs is False


class TestGetMtfSummary:
    def _mock_prepare(self, trend="up", n=300):
        return _make_df(n, trend)

    def test_weekly_too_short_permits_both(self):
        from app.analysis.multi_tf import get_mtf_summary
        with patch("app.analysis.multi_tf._prepare_df", return_value=_make_df(100)):
            result = get_mtf_summary("BTCUSDT")
        assert result["weekly_permit_long"] is True
        assert result["weekly_permit_short"] is True

    def test_bull_weekly_blocks_short(self):
        from app.analysis.multi_tf import get_mtf_summary
        df_bull = _make_df(300, trend="up")
        with patch("app.analysis.multi_tf._prepare_df", return_value=df_bull), \
             patch("app.analysis.multi_tf.trend_filter_ema", return_value="BULL"), \
             patch("app.analysis.multi_tf._h4_structure_confirm", return_value=(True, False, "ok")):
            result = get_mtf_summary("BTCUSDT")
        assert result["weekly_permit_short"] is False

    def test_bear_weekly_blocks_long(self):
        from app.analysis.multi_tf import get_mtf_summary
        df_bear = _make_df(300, trend="down")
        with patch("app.analysis.multi_tf._prepare_df", return_value=df_bear), \
             patch("app.analysis.multi_tf.trend_filter_ema", return_value="BEAR"), \
             patch("app.analysis.multi_tf._h4_structure_confirm", return_value=(False, True, "ok")):
            result = get_mtf_summary("BTCUSDT")
        assert result["weekly_permit_long"] is False

    def test_returns_required_keys(self):
        from app.analysis.multi_tf import get_mtf_summary
        with patch("app.analysis.multi_tf._prepare_df", return_value=_make_df(100)):
            result = get_mtf_summary("BTCUSDT")
        for key in ["symbol", "weekly_trend", "h4_trend",
                    "weekly_permit_long", "weekly_permit_short",
                    "h4_confirm_long", "h4_confirm_short"]:
            assert key in result

    def test_symbol_in_result(self):
        from app.analysis.multi_tf import get_mtf_summary
        with patch("app.analysis.multi_tf._prepare_df", return_value=_make_df(100)):
            result = get_mtf_summary("ETHUSDT")
        assert result["symbol"] == "ETHUSDT"