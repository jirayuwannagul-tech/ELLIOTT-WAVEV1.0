from app.analysis.wave_scenarios import build_scenarios


def test_empty_wave_input():
    result = build_scenarios([])
    assert result == []


def test_invalid_wave_structure():
    result = build_scenarios([{"type": "UNKNOWN"}])
    assert result == []


def test_valid_impulse_scenario():
    pivots = [
        {"type": "L", "price": 100, "index": 1, "degree": "intermediate"},
        {"type": "H", "price": 120, "index": 2, "degree": "intermediate"},
        {"type": "L", "price": 110, "index": 3, "degree": "intermediate"},
        {"type": "H", "price": 140, "index": 4, "degree": "intermediate"},
        {"type": "L", "price": 130, "index": 5, "degree": "intermediate"},
        {"type": "H", "price": 150, "index": 6, "degree": "intermediate"},
    ]

    result = build_scenarios(
        pivots,
        macro_trend="BULL",
        rsi14=55.0,
        volume_spike=False,
        symbol="BTCUSDT",
    )

    assert isinstance(result, list)