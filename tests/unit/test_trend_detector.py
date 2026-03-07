# tests/unit/test_trend_detector.py
import pytest
import pandas as pd
from app.analysis.trend_detector import detect_market_mode


def _make_df(ema50=110.0, ema200=100.0, atr=2.0, close=100.0):
    return pd.DataFrame({
        "close":  [close],
        "ema50":  [ema50],
        "ema200": [ema200],
        "atr14":  [atr],
    })


class TestDetectMarketMode:
    def test_no_ema_columns_returns_trend(self):
        df = pd.DataFrame({"close": [100.0]})
        assert detect_market_mode(df) == "TREND"

    def test_strong_trend_returns_trend(self):
        # EMA gap ใหญ่ → TREND
        df = _make_df(ema50=120.0, ema200=100.0, atr=2.0, close=100.0)
        assert detect_market_mode(df) == "TREND"

    def test_sideway_small_gap_low_atr(self):
        # ema_gap_pct < 0.5 และ atr/price < 0.02 → SIDEWAY
        df = _make_df(ema50=100.3, ema200=100.0, atr=1.0, close=100.0)
        assert detect_market_mode(df) == "SIDEWAY"

    def test_small_gap_high_atr_returns_trend(self):
        # ema_gap ต่ำ แต่ atr สูง → TREND
        df = _make_df(ema50=100.3, ema200=100.0, atr=5.0, close=100.0)
        assert detect_market_mode(df) == "TREND"

    def test_large_gap_low_atr_returns_trend(self):
        # ema_gap สูง แม้ atr ต่ำ → TREND
        df = _make_df(ema50=110.0, ema200=100.0, atr=0.5, close=100.0)
        assert detect_market_mode(df) == "TREND"

    def test_no_atr_column_small_gap_returns_sideway(self):
        # ไม่มี atr14 → atr=0.0 + ema gap เล็ก → SIDEWAY
        df = pd.DataFrame({
            "close":  [100.0],
            "ema50":  [100.3],
            "ema200": [100.0],
        })
        assert detect_market_mode(df) == "SIDEWAY"

    def test_returns_string(self):
        df = _make_df()
        result = detect_market_mode(df)
        assert isinstance(result, str)
        assert result in ("TREND", "SIDEWAY")