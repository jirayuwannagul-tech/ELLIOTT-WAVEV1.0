import pytest
from app.analysis.wave_engine import analyze_symbol

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT",
]

REQUIRED_KEYS = ["symbol", "price", "macro_trend", "rsi14", "volume_spike", "scenarios"]

@pytest.mark.parametrize("symbol", SYMBOLS)
def test_wave_engine_smoke(symbol):
    result = analyze_symbol(symbol)
    assert result is not None, f"{symbol}: result เป็น None"
    assert isinstance(result, dict), f"{symbol}: result ไม่ใช่ dict"
    for k in REQUIRED_KEYS:
        assert k in result, f"{symbol}: ไม่มี key '{k}'"
    assert isinstance(result["scenarios"], list), f"{symbol}: scenarios ไม่ใช่ list"
    assert result["price"] > 0, f"{symbol}: price ต้องมากกว่า 0"
    for sc in result["scenarios"]:
        assert "direction" in sc, f"{symbol}: scenario ไม่มี direction"
        assert "trade_plan" in sc, f"{symbol}: scenario ไม่มี trade_plan"
        assert sc["direction"] in ("LONG", "SHORT"), f"{symbol}: direction ไม่ถูกต้อง"