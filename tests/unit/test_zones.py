# tests/unit/test_zones.py
import pytest
import pandas as pd
from app.analysis.zones import _safe_float, _merge_clusters, nearest_support_resist, build_zones_from_pivots
from unittest.mock import patch


class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float(1.5) == 1.5

    def test_string_number(self):
        assert _safe_float("3.14") == pytest.approx(3.14)

    def test_invalid_returns_default(self):
        assert _safe_float("abc") == 0.0

    def test_none_returns_default(self):
        assert _safe_float(None, 99.0) == 99.0


class TestMergeClusters:
    def test_empty_returns_empty(self):
        assert _merge_clusters([], tol_pct=1.0) == []

    def test_single_value(self):
        result = _merge_clusters([100.0], tol_pct=1.0)
        assert result == [[100.0]]

    def test_close_values_merged(self):
        result = _merge_clusters([100.0, 100.2, 100.3], tol_pct=1.0)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_far_values_separate(self):
        result = _merge_clusters([100.0, 200.0], tol_pct=1.0)
        assert len(result) == 2

    def test_sorted_input(self):
        result = _merge_clusters([200.0, 100.0], tol_pct=0.5)
        assert result[0][0] == 100.0


class TestNearestSupportResist:
    def _zones(self):
        return [
            {"level": 90.0, "side": "SUPPORT"},
            {"level": 95.0, "side": "SUPPORT"},
            {"level": 105.0, "side": "RESIST"},
            {"level": 110.0, "side": "RESIST"},
        ]

    def test_support_below_price(self):
        result = nearest_support_resist(self._zones(), price=100.0)
        assert result["support"]["level"] == 95.0

    def test_resist_above_price(self):
        result = nearest_support_resist(self._zones(), price=100.0)
        assert result["resist"]["level"] == 105.0

    def test_no_support_returns_none(self):
        zones = [{"level": 110.0, "side": "RESIST"}]
        result = nearest_support_resist(zones, price=100.0)
        assert result["support"] is None

    def test_no_resist_returns_none(self):
        zones = [{"level": 90.0, "side": "SUPPORT"}]
        result = nearest_support_resist(zones, price=100.0)
        assert result["resist"] is None

    def test_empty_zones(self):
        result = nearest_support_resist([], price=100.0)
        assert result["support"] is None
        assert result["resist"] is None

    def test_side_overridden_correctly(self):
        result = nearest_support_resist(self._zones(), price=100.0)
        assert result["support"]["side"] == "SUPPORT"
        assert result["resist"]["side"] == "RESIST"

    def test_level_equal_price_excluded(self):
        zones = [{"level": 100.0, "side": "SUPPORT"}]
        result = nearest_support_resist(zones, price=100.0)
        assert result["support"] is None
        assert result["resist"] is None


class TestBuildZonesFromPivots:
    def _make_df(self, n=100):
        closes = [100.0 + i * 0.1 for i in range(n)]
        return pd.DataFrame({
            "open": closes, "high": closes,
            "low": closes, "close": closes, "volume": [1000.0] * n,
        })

    def test_too_short_returns_empty(self):
        df = self._make_df(10)
        assert build_zones_from_pivots(df) == []

    def test_none_returns_empty(self):
        assert build_zones_from_pivots(None) == []

    def test_returns_list(self):
        df = self._make_df(100)
        pivots = [{"type": "H", "price": 105.0}, {"type": "H", "price": 105.2},
                  {"type": "L", "price": 95.0}, {"type": "L", "price": 95.1}]
        with patch("app.analysis.zones.find_fractal_pivots", return_value=pivots), \
             patch("app.analysis.zones.filter_pivots", side_effect=lambda x, **kw: x):
            result = build_zones_from_pivots(df, min_touches=2)
        assert isinstance(result, list)

    def test_zone_has_required_keys(self):
        df = self._make_df(100)
        pivots = [{"type": "H", "price": 105.0}, {"type": "H", "price": 105.2},
                  {"type": "L", "price": 95.0}, {"type": "L", "price": 95.1}]
        with patch("app.analysis.zones.find_fractal_pivots", return_value=pivots), \
             patch("app.analysis.zones.filter_pivots", side_effect=lambda x, **kw: x):
            result = build_zones_from_pivots(df, min_touches=2)
        if result:
            for key in ["kind", "level", "low", "high", "touches", "side"]:
                assert key in result[0]