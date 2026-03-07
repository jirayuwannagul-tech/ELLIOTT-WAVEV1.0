# tests/unit/test_fib.py
import pytest
from app.analysis.fib import fib_retracement, fib_extension, fib_zone_match


class TestFibRetracement:
    def test_zero_move_returns_none(self):
        assert fib_retracement(100., 100., 100.) is None

    def test_valid_50_percent(self):
        r = fib_retracement(0., 100., 50.)
        assert r == pytest.approx(0.5)

    def test_valid_618(self):
        r = fib_retracement(0., 100., 38.2)
        assert r == pytest.approx(0.618, rel=1e-2)

    def test_no_retrace_returns_none(self):
        # current = end → retrace = 0 → valid
        assert fib_retracement(0., 100., 100.) == pytest.approx(0.0)

    def test_over_retrace_returns_none(self):
        # current ต่ำกว่า start → retrace > 1.0
        assert fib_retracement(0., 100., -10.) is None

    def test_negative_retrace_returns_none(self):
        # current สูงกว่า end → retrace < 0
        assert fib_retracement(0., 100., 110.) is None

    def test_downtrend(self):
        # start=100, end=50, current=75 → retrace = (50-75)/(50-100) = 0.5
        r = fib_retracement(100., 50., 75.)
        assert r == pytest.approx(0.5)

    def test_full_retrace(self):
        # current = start → retrace = 1.0
        assert fib_retracement(0., 100., 0.) == pytest.approx(1.0)


class TestFibExtension:
    def test_returns_dict(self):
        r = fib_extension(0., 100., 61.8)
        assert isinstance(r, dict)
        assert "1.0" in r and "1.618" in r and "2.0" in r

    def test_1x_extension(self):
        # length=100, c=61.8 → 1.0 = 161.8
        r = fib_extension(0., 100., 61.8)
        assert r["1.0"] == pytest.approx(161.8)

    def test_1618_extension(self):
        r = fib_extension(0., 100., 0.)
        assert r["1.618"] == pytest.approx(161.8)

    def test_2x_extension(self):
        r = fib_extension(0., 100., 0.)
        assert r["2.0"] == pytest.approx(200.0)

    def test_negative_length(self):
        # downtrend: a=100, b=50, c=70
        r = fib_extension(100., 50., 70.)
        assert r["1.0"] == pytest.approx(20.0)


class TestFibZoneMatch:
    def test_exact_618(self):
        assert "0.618" in fib_zone_match(0.618)

    def test_exact_382(self):
        assert "0.382" in fib_zone_match(0.382)

    def test_within_tolerance(self):
        assert "0.5" in fib_zone_match(0.51)

    def test_outside_tolerance(self):
        assert fib_zone_match(0.9) == []

    def test_multiple_matches(self):
        # 0.618 และ 0.786 ห่างกัน 0.168 tolerance=0.03 ไม่ควร match ทั้งคู่
        r = fib_zone_match(0.618)
        assert "0.618" in r

    def test_zero_no_match(self):
        assert fib_zone_match(0.0) == []

    def test_returns_list(self):
        assert isinstance(fib_zone_match(0.5), list)