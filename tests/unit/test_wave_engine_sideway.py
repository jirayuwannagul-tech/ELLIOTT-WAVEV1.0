import pandas as pd
from app.analysis.wave_engine import run_sideway_engine


def test_sideway_no_range():
    df = pd.DataFrame({"low":[1,2], "high":[2,3]})
    base = {"price":2, "rsi14":50}

    result = run_sideway_engine("BTCUSDT", df, base)

    assert result["scenarios"] == []


def test_sideway_long_setup():
    df = pd.DataFrame({
        "low":[100,101,102,103,104,105],
        "high":[110,111,112,113,114,115],
        "atr14":[1,1,1,1,1,1],
    })

    base = {
        "price":100,
        "rsi14":40,
        "weekly_permit_long":True,
        "weekly_permit_short":True,
    }

    result = run_sideway_engine("BTCUSDT", df, base)

    assert isinstance(result["scenarios"], list)


def test_sideway_short_setup():
    df = pd.DataFrame({
        "low":[100,101,102,103,104,105],
        "high":[110,111,112,113,114,115],
        "atr14":[1,1,1,1,1,1],
    })

    base = {
        "price":115,
        "rsi14":60,
        "weekly_permit_long":True,
        "weekly_permit_short":True,
    }

    result = run_sideway_engine("BTCUSDT", df, base)

    assert isinstance(result["scenarios"], list)