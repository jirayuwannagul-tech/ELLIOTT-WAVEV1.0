from app.trading import trade_executor


def test_build_plan_valid():
    plan = {
        "valid": True,
        "entry": 100,
        "sl": 95,
        "tp1": 105,
        "tp2": 110,
    }

    assert plan["valid"] is True
    assert plan["entry"] > plan["sl"]
    assert plan["tp1"] > plan["entry"]
    assert plan["tp2"] > plan["tp1"]