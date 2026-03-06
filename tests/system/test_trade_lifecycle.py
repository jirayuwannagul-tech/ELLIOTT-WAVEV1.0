from unittest.mock import patch

from app.analysis.wave_engine import analyze_symbol


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.build_scenarios")
def test_trade_lifecycle(fetch, drop, build_scenarios):

    import pandas as pd

    rows = 300
    df = pd.DataFrame({
        "open":[100]*rows,
        "high":[105]*rows,
        "low":[95]*rows,
        "close":[101]*rows,
        "volume":[1000]*rows
    })

    fetch.return_value = df
    drop.return_value = df

    build_scenarios.return_value = [
        {
            "type":"ABC_UP",
            "direction":"LONG",
            "confidence":70
        }
    ]

    result = analyze_symbol("BTCUSDT")

    assert result is not None
    assert "scenarios" in result