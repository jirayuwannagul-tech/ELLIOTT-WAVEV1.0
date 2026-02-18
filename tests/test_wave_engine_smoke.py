import pytest
from app.analysis.wave_engine import analyze_symbol


def test_wave_engine_smoke():
    result = analyze_symbol("BTCUSDT")

    # ต้องไม่ None
    assert result is not None

    # ต้องเป็น dict
    assert isinstance(result, dict)

    # key หลักต้องมี
    required_keys = [
        "symbol",
        "price",
        "macro_trend",
        "rsi14",
        "volume_spike",
        "scenarios",
    ]

    for k in required_keys:
        assert k in result