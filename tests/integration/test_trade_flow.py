import pandas as pd
from unittest.mock import patch

from app.analysis.wave_engine import analyze_symbol


@patch("app.analysis.wave_engine.build_trade_plan")
@patch("app.analysis.wave_engine.build_scenarios")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.fetch_ohlcv")
def test_trade_flow(fetch_ohlcv_mock, drop_mock, build_scenarios_mock, build_trade_plan_mock):
    rows = 300
    df = pd.DataFrame({
        "open": [100] * rows,
        "high": [105] * rows,
        "low": [95] * rows,
        "close": [101] * rows,
        "volume": [1000] * rows,
    })

    fetch_ohlcv_mock.return_value = df
    drop_mock.return_value = df

    build_scenarios_mock.return_value = [
        {
            "type": "ABC_UP",
            "phase": "CORRECTION",
            "direction": "LONG",
            "confidence": 70,
            "probability": 0.6,
            "reasons": ["test scenario"],
            "pivots": [
                {"price": 95, "type": "L"},
                {"price": 105, "type": "H"},
                {"price": 98, "type": "L"},
                {"price": 108, "type": "H"},
            ],
        }
    ]

    build_trade_plan_mock.return_value = {
        "entry": 100,
        "sl": 95,
        "tp1": 105,
        "tp2": 110,
        "valid": True,
        "triggered": True,
    }

    result = analyze_symbol("BTCUSDT")

    assert result is not None
    assert "scenarios" in result