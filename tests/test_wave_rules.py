from app.analysis.wave_rules import validate_impulse, validate_abc


def test_validate_impulse_structure_only():
    points = [
        {"type": "L", "price": 100},
        {"type": "H", "price": 120},
        {"type": "L", "price": 110},
        {"type": "H", "price": 140},
        {"type": "L", "price": 130},
        {"type": "H", "price": 160},
    ]

    ok, reasons = validate_impulse(points, "LONG")
    assert isinstance(ok, bool)
    assert isinstance(reasons, list)


def test_validate_abc_structure_only():
    points = [
        {"type": "L", "price": 100},
        {"type": "H", "price": 120},
        {"type": "L", "price": 110},
        {"type": "H", "price": 130},
    ]

    ok, reasons = validate_abc(points, "UP")
    assert isinstance(ok, bool)
    assert isinstance(reasons, list)