import pandas as pd
from app.analysis.wave_engine import _range_levels


def test_range_levels_normal():

    df = pd.DataFrame({
        "low": list(range(1,21)),
        "high": list(range(21,41)),
        "atr14": [1]*20
    })

    result = _range_levels(df, lookback=5)

    assert result["range_low"] == 16
    assert result["range_high"] == 40