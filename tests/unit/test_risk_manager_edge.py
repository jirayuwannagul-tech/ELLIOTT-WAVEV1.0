import pytest
from app.risk.risk_manager import calculate_rr, recalculate_from_fill


def test_rr_exact_boundary():
    rr = calculate_rr(100, 90, 115)
    assert rr >= 1.5


def test_rr_zero_division():
    rr = calculate_rr(100, 100, 120)
    assert rr == 0.0


def test_recalculate_long_sl_above_entry_invalid():
    result = recalculate_from_fill(
        direction="LONG",
        actual_entry=100,
        original_sl=105,
        original_tp_rr=1.618,
        min_rr=1.5,
    )
    assert result["valid"] is True


def test_recalculate_short_sl_below_entry_invalid():
    result = recalculate_from_fill(
        direction="SHORT",
        actual_entry=100,
        original_sl=95,
        original_tp_rr=1.618,
        min_rr=1.5,
    )
    assert result["valid"] is True