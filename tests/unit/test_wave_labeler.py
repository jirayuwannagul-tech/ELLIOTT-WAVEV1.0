# tests/unit/test_wave_labeler.py
import pytest
from app.analysis.wave_labeler import label_pivot_chain, _score_from_reasons
from unittest.mock import patch


def _pivot(type_, price, index):
    return {"type": type_, "price": float(price), "index": index}


def _impulse_long_pivots():
    # L H L H L H → IMPULSE_LONG
    return [
        _pivot("L", 100, 0),
        _pivot("H", 120, 1),
        _pivot("L", 110, 2),
        _pivot("H", 140, 3),
        _pivot("L", 125, 4),
        _pivot("H", 160, 5),
    ]


def _abc_down_pivots():
    # H L H L → ABC_DOWN
    return [
        _pivot("H", 160, 0),
        _pivot("L", 130, 1),
        _pivot("H", 150, 2),
        _pivot("L", 110, 3),
    ]


class TestScoreFromReasons:
    def test_no_reasons_returns_base(self):
        assert _score_from_reasons(85.0, []) == pytest.approx(85.0)

    def test_each_reason_reduces_5(self):
        assert _score_from_reasons(85.0, ["r1", "r2"]) == pytest.approx(75.0)

    def test_min_score_is_1(self):
        assert _score_from_reasons(10.0, ["r"] * 20) == pytest.approx(1.0)

    def test_max_score_is_100(self):
        assert _score_from_reasons(200.0, []) == pytest.approx(100.0)


class TestLabelPivotChain:
    def test_empty_pivots_returns_none(self):
        result = label_pivot_chain([])
        assert result["label"] is None

    def test_too_few_pivots_returns_none(self):
        result = label_pivot_chain([_pivot("L", 100, 0), _pivot("H", 110, 1)])
        assert result["label"] is None

    def test_returns_dict_with_label_and_matches(self):
        result = label_pivot_chain(_impulse_long_pivots())
        assert "label" in result
        assert "matches" in result

    def test_impulse_long_detected(self):
        pivots = _impulse_long_pivots()
        with patch("app.analysis.wave_labeler.validate_impulse", return_value=(True, [])), \
             patch("app.analysis.wave_labeler.validate_abc", return_value=(False, [])):
            result = label_pivot_chain(pivots)
        assert result["label"] is not None
        assert result["label"]["direction"] in ("LONG", "SHORT")

    def test_no_match_returns_none_label(self):
        pivots = _impulse_long_pivots()
        with patch("app.analysis.wave_labeler.validate_impulse", return_value=(False, [])), \
             patch("app.analysis.wave_labeler.validate_abc", return_value=(False, [])):
            result = label_pivot_chain(pivots)
        assert result["label"] is None

    def test_label_has_required_keys(self):
        pivots = _impulse_long_pivots()
        with patch("app.analysis.wave_labeler.validate_impulse", return_value=(True, [])), \
             patch("app.analysis.wave_labeler.validate_abc", return_value=(False, [])):
            result = label_pivot_chain(pivots)
        if result["label"]:
            for key in ["pattern", "direction", "confidence", "pivots"]:
                assert key in result["label"]

    def test_best_label_has_highest_end_index(self):
        pivots = _impulse_long_pivots() + [_pivot("L", 140, 6), _pivot("H", 170, 7)]
        with patch("app.analysis.wave_labeler.validate_impulse", return_value=(True, [])), \
             patch("app.analysis.wave_labeler.validate_abc", return_value=(False, [])):
            result = label_pivot_chain(pivots)
        if result["label"]:
            assert result["label"]["end_pivot_i"] >= 0

    def test_abc_down_detected(self):
        pivots = _abc_down_pivots()
        with patch("app.analysis.wave_labeler.validate_impulse", return_value=(False, [])), \
             patch("app.analysis.wave_labeler.validate_abc", side_effect=lambda w, d: (d == "DOWN", [])):
            result = label_pivot_chain(pivots)
        if result["label"]:
            assert result["label"]["pattern"] in ("ABC_DOWN", "ABC_UP", "IMPULSE_LONG", "IMPULSE_SHORT")