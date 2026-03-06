from app.trading import trade_executor


def test_plan_structure():
    plan = {
        "entry": 100,
        "sl": 95,
        "tp1": 105,
        "tp2": 110,
        "valid": True
    }

    assert plan["entry"] > plan["sl"]
    assert plan["tp1"] > plan["entry"]
    assert plan["tp2"] > plan["tp1"]
    assert plan["valid"]


def test_invalid_plan():
    plan = {
        "entry": 100,
        "sl": 105,
        "valid": False
    }

    assert plan["valid"] is False