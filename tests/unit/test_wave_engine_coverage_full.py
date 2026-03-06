import pandas as pd
from unittest.mock import patch

from app.analysis.wave_engine import analyze_symbol


def fake_df():
    rows = 300
    data = {
        "open": [100]*rows,
        "high": [105]*rows,
        "low": [95]*rows,
        "close": [100]*rows,
        "volume": [1000]*rows,
    }
    df = pd.DataFrame(data)
    return df


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
def test_not_enough_bars(fetch, drop):
    fetch.return_value = fake_df().iloc[:100]
    drop.return_value = fetch.return_value

    r = analyze_symbol("BTCUSDT")
    assert r is None


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.detect_market_mode")
def test_sideway_path(mode, fetch, drop):
    fetch.return_value = fake_df()
    drop.return_value = fetch.return_value
    mode.return_value = "SIDEWAY"

    r = analyze_symbol("BTCUSDT")
    assert r is not None
    assert "sideway" in r


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.find_fractal_pivots")
def test_not_enough_pivots(pivots, fetch, drop):
    fetch.return_value = fake_df()
    drop.return_value = fetch.return_value
    pivots.return_value = []

    r = analyze_symbol("BTCUSDT")
    assert r is not None
    assert r["scenarios"] == []


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.find_fractal_pivots")
@patch("app.analysis.wave_engine.filter_pivots")
@patch("app.analysis.wave_engine.build_scenarios")
def test_direction_empty(build, filt, pivots, fetch, drop):

    fetch.return_value = fake_df()
    drop.return_value = fetch.return_value

    pivots.return_value = [{"price":100}]
    filt.return_value = pivots.return_value

    build.return_value = [
        {"direction": "", "confidence":50}
    ]

    r = analyze_symbol("BTCUSDT")
    assert r is not None


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.find_fractal_pivots")
@patch("app.analysis.wave_engine.filter_pivots")
@patch("app.analysis.wave_engine.build_scenarios")
@patch("app.analysis.wave_engine.build_trade_plan")
def test_entry_none(plan, build, filt, pivots, fetch, drop):

    fetch.return_value = fake_df()
    drop.return_value = fetch.return_value

    pivots.return_value = [
        {"price":100, "type":"L"},
        {"price":101, "type":"H"},
        {"price":99,  "type":"L"},
        {"price":102, "type":"H"},
        {"price":98,  "type":"L"},
    ]
    filt.return_value = pivots.return_value

    build.return_value = [
        {"direction":"LONG","confidence":70}
    ]

    plan.return_value = {
        "entry": None,
        "valid": False
    }

    r = analyze_symbol("BTCUSDT")
    assert r is not None


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.find_fractal_pivots")
@patch("app.analysis.wave_engine.filter_pivots")
@patch("app.analysis.wave_engine.build_scenarios")
@patch("app.analysis.wave_engine.build_trade_plan")
def test_trigger_logic(plan, build, filt, pivots, fetch, drop):

    fetch.return_value = fake_df()
    drop.return_value = fetch.return_value

    pivots.return_value = [
        {"price":100, "type":"L"},
        {"price":101, "type":"H"},
        {"price":99,  "type":"L"},
        {"price":102, "type":"H"},
        {"price":98,  "type":"L"},
    ]
    filt.return_value = pivots.return_value

    build.return_value = [
        {"direction":"LONG","confidence":70,"type":"ABC_UP"}
    ]

    plan.return_value = {
        "entry":100,
        "valid":True
    }

    r = analyze_symbol("BTCUSDT")
    assert r is not None


@patch("app.analysis.wave_engine.fetch_ohlcv")
@patch("app.analysis.wave_engine.drop_unclosed_candle")
@patch("app.analysis.wave_engine.find_fractal_pivots")
@patch("app.analysis.wave_engine.filter_pivots")
@patch("app.analysis.wave_engine.build_scenarios")
@patch("app.analysis.wave_engine.build_trade_plan")
def test_blocked_trade(plan, build, filt, pivots, fetch, drop):

    fetch.return_value = fake_df()
    drop.return_value = fetch.return_value

    pivots.return_value = [
        {"price":100, "type":"L"},
        {"price":101, "type":"H"},
        {"price":99,  "type":"L"},
        {"price":102, "type":"H"},
        {"price":98,  "type":"L"},
    ]
    filt.return_value = pivots.return_value

    build.return_value = [
        {"direction":"SHORT","confidence":40}
    ]

    plan.return_value = {
        "entry":100,
        "valid":False
    }

    r = analyze_symbol("BTCUSDT")
    assert r is not None