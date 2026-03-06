from app.analysis.wave_engine import _safe_float


def test_safe_float_valid():
    assert _safe_float("10") == 10.0


def test_safe_float_invalid():
    assert _safe_float("abc") == 0.0