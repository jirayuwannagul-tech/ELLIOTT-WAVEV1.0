# tests/unit/test_market_regime.py
import pytest
import pandas as pd
from app.analysis.market_regime import detect_market_regime, _safe_float, _pct


def _make_df(n=250, ema50=110.0, ema200=100.0, atr=2.0, rsi=55.0, close=120.0):
    return pd.DataFrame({
        "close":  [close] * n,
        "ema50":  [ema50] * n,
        "ema200": [ema200] * n,
        "atr14":  [atr] * n,
        "rsi14":  [rsi] * n,
    })


class TestSafeFloat:
    def test_valid(self):
        assert _safe_float(1.5) == 1.5

    def test_invalid_returns_default(self):
        assert _safe_float("abc", 99.0) == 99.0


class TestPct:
    def test_zero_b(self):
        assert _pct(100.0, 0.0) == 0.0

    def test_10_percent(self):
        assert _pct(110.0, 100.0) == pytest.approx(10.0)


class TestDetectMarketRegime:
    def test_too_short_returns_chop(self):
        df = _make_df(100)
        result = detect_market_regime(df)
        assert result["regime"] == "CHOP"
        assert result["trend"] == "NEUTRAL"
        assert "len<250" in result["notes"]

    def test_none_returns_chop(self):
        result = detect_market_regime(None)
        assert result["regime"] == "CHOP"

    def test_bull_trend(self):
        # ema50 > ema200, slope ขึ้น → BULL
        closes = [100.0 + i * 0.1 for i in range(250)]
        ema50  = [100.0 + i * 0.12 for i in range(250)]
        ema200 = [100.0 + i * 0.05 for i in range(250)]
        df = pd.DataFrame({
            "close":  closes,
            "ema50":  ema50,
            "ema200": ema200,
            "atr14":  [2.0] * 250,
            "rsi14":  [60.0] * 250,
        })
        result = detect_market_regime(df)
        assert result["trend"] == "BULL"

    def test_bear_trend(self):
        closes = [200.0 - i * 0.1 for i in range(250)]
        ema50  = [200.0 - i * 0.12 for i in range(250)]
        ema200 = [200.0 - i * 0.05 for i in range(250)]
        df = pd.DataFrame({
            "close":  closes,
            "ema50":  ema50,
            "ema200": ema200,
            "atr14":  [2.0] * 250,
            "rsi14":  [40.0] * 250,
        })
        result = detect_market_regime(df)
        assert result["trend"] == "BEAR"

    def test_trend_regime_when_large_gap(self):
        # ema_gap >= 1% + same slope → TREND
        df = _make_df(250, ema50=110.0, ema200=100.0, atr=2.0, rsi=60.0, close=120.0)
        # slope ต้องไปทางเดียวกัน → ทำ 2 แถวสุดท้ายต่างกัน
        df.loc[df.index[-2], "ema50"] = 109.0
        df.loc[df.index[-2], "ema200"] = 99.0
        result = detect_market_regime(df)
        assert result["regime"] == "TREND"

    def test_range_regime(self):
        # ema_gap <= 0.5% + RSI กลาง → RANGE
        df = _make_df(250, ema50=100.2, ema200=100.0, atr=1.0, rsi=50.0, close=100.0)
        result = detect_market_regime(df)
        assert result["regime"] == "RANGE"

    def test_low_vol(self):
        df = _make_df(250, atr=1.0, close=100.0)
        result = detect_market_regime(df)
        assert result["vol"] == "LOW"

    def test_high_vol(self):
        df = _make_df(250, atr=5.0, close=100.0)
        result = detect_market_regime(df)
        assert result["vol"] == "HIGH"

    def test_returns_required_keys(self):
        df = _make_df()
        result = detect_market_regime(df)
        for key in ["regime", "trend", "vol", "trend_strength", "vol_score", "notes"]:
            assert key in result

    def test_trend_strength_in_range(self):
        df = _make_df()
        result = detect_market_regime(df)
        assert 0.0 <= result["trend_strength"] <= 100.0