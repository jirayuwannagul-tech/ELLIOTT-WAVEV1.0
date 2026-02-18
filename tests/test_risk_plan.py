from app.risk.risk_manager import build_trade_plan


def test_build_trade_plan_long_basic():
    scenario = {
        "direction": "LONG",
        "pivots": [
            {"price": 100},
            {"price": 120},
            {"price": 110},
            {"price": 130},
        ],
        "type": "ABC_UP",
    }

    trade = build_trade_plan(
        scenario,
        current_price=125,
        min_rr=1.5,
    )

    assert isinstance(trade, dict)
    assert "valid" in trade