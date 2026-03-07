# tests/unit/test_position_sizer.py
import pytest
from app.trading.position_sizer import calculate_quantity


class TestCalculateQuantity:
    def test_basic_calculation(self):
        # balance=1000, risk=1%, entry=100, sl=90 → risk_amount=10, sl_dist=10 → qty=1.0
        result = calculate_quantity(1000.0, 0.01, 100.0, 90.0)
        assert result == pytest.approx(1.0)

    def test_zero_sl_distance_returns_zero(self):
        # entry == sl → ไม่ควรหาร 0
        result = calculate_quantity(1000.0, 0.01, 100.0, 100.0)
        assert result == 0.0

    def test_short_position(self):
        # entry=100, sl=110 → sl_dist=10
        result = calculate_quantity(1000.0, 0.01, 100.0, 110.0)
        assert result == pytest.approx(1.0)

    def test_small_risk_pct(self):
        result = calculate_quantity(1000.0, 0.005, 100.0, 90.0)
        assert result == pytest.approx(0.5)

    def test_returns_float(self):
        result = calculate_quantity(1000.0, 0.01, 100.0, 90.0)
        assert isinstance(result, float)

    def test_large_sl_distance_small_qty(self):
        # sl_dist=50 → qty = 10/50 = 0.2
        result = calculate_quantity(1000.0, 0.01, 100.0, 50.0)
        assert result == pytest.approx(0.2)

    def test_zero_balance_returns_zero(self):
        result = calculate_quantity(0.0, 0.01, 100.0, 90.0)
        assert result == 0.0