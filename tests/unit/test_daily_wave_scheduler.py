# tests/unit/test_daily_wave_scheduler.py
import pytest
from unittest.mock import patch, MagicMock
import os


def _make_analysis(symbol="BTCUSDT", conf=90.0, direction="SHORT", price=100.0, triggered=True):
    return {
        "symbol": symbol,
        "price": price,
        "scenarios": [{
            "direction": direction,
            "confidence": conf,
            "status": "READY",
            "trade_plan": {
                "valid": True,
                "triggered": triggered,
                "allowed_to_trade": True,
                "entry": price,
                "sl": price * 1.05,
                "tp1": price * 0.95,
                "tp2": price * 0.90,
                "tp3": price * 0.85,
            }
        }],
        "wave_label": {"label": {"pattern": "ABC", "direction": direction, "confidence": conf}},
        "sr": {"support": {"level": 90.0}, "resist": {"level": 110.0}},
    }


class TestFmtPrice:
    def test_above_1(self):
        from app.scheduler.daily_wave_scheduler import _fmt_price
        assert "," in _fmt_price(1234.5) or "." in _fmt_price(1234.5)

    def test_below_1(self):
        from app.scheduler.daily_wave_scheduler import _fmt_price
        result = _fmt_price(0.5)
        assert "0.50000" in result

    def test_returns_string(self):
        from app.scheduler.daily_wave_scheduler import _fmt_price
        assert isinstance(_fmt_price(100.0), str)


class TestPctNear:
    def test_same_price(self):
        from app.scheduler.daily_wave_scheduler import _pct_near
        assert _pct_near(100.0, 100.0) == pytest.approx(0.0)

    def test_zero_b(self):
        from app.scheduler.daily_wave_scheduler import _pct_near
        assert _pct_near(100.0, 0.0) == 999.0

    def test_1_percent(self):
        from app.scheduler.daily_wave_scheduler import _pct_near
        assert _pct_near(101.0, 100.0) == pytest.approx(1.0)


class TestCheckPositionFromVps:
    def test_no_vps_url_returns_false(self):
        from app.scheduler.daily_wave_scheduler import _check_position_from_vps
        with patch.dict(os.environ, {"VPS_URL": "", "EXEC_TOKEN": ""}):
            assert _check_position_from_vps("BTCUSDT") is False

    def test_vps_active_true(self):
        from app.scheduler.daily_wave_scheduler import _check_position_from_vps
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"active": True}
        with patch.dict(os.environ, {"VPS_URL": "http://fake", "EXEC_TOKEN": "tok"}), \
             patch("app.scheduler.daily_wave_scheduler.req.get", return_value=mock_resp):
            assert _check_position_from_vps("BTCUSDT") is True

    def test_vps_exception_returns_false(self):
        from app.scheduler.daily_wave_scheduler import _check_position_from_vps
        with patch.dict(os.environ, {"VPS_URL": "http://fake", "EXEC_TOKEN": "tok"}), \
             patch("app.scheduler.daily_wave_scheduler.req.get", side_effect=Exception("timeout")):
            assert _check_position_from_vps("BTCUSDT") is False


class TestRunTrendWatchJob:
    def test_no_signals_sends_empty(self):
        from app.scheduler.daily_wave_scheduler import run_trend_watch_job
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send:
            run_trend_watch_job(min_conf=65.0)
        msg = mock_send.call_args[0][0]
        assert "TREND WATCH" in msg
        assert "0" in msg

    def test_high_conf_signal_included(self):
        from app.scheduler.daily_wave_scheduler import run_trend_watch_job
        analysis = _make_analysis(conf=90.0)
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=analysis), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send:
            run_trend_watch_job(min_conf=65.0)
        msg = mock_send.call_args[0][0]
        assert "BTCUSDT" in msg

    def test_low_conf_signal_excluded(self):
        from app.scheduler.daily_wave_scheduler import run_trend_watch_job
        analysis = _make_analysis(conf=50.0)
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=analysis), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send:
            run_trend_watch_job(min_conf=65.0)
        msg = mock_send.call_args[0][0]
        assert "จำนวนที่น่าจับตา: 0" in msg

    def test_timestamp_in_message(self):
        from app.scheduler.daily_wave_scheduler import run_trend_watch_job
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send:
            run_trend_watch_job()
        msg = mock_send.call_args[0][0]
        assert "📅" in msg


class TestRunDailyWaveJob:
    def test_no_analysis_no_signal(self):
        from app.scheduler.daily_wave_scheduler import run_daily_wave_job
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send, \
             patch("app.scheduler.daily_wave_scheduler.get_active", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler.get_armed_signal", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler._check_position_from_vps", return_value=False):
            run_daily_wave_job()
        summary = mock_send.call_args[0][0]
        assert "พบสัญญาณ: 0" in summary

    def test_active_position_skips(self):
        from app.scheduler.daily_wave_scheduler import run_daily_wave_job
        mock_pos = MagicMock()
        mock_pos.status = "ACTIVE"
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=_make_analysis()), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send, \
             patch("app.scheduler.daily_wave_scheduler.get_active", return_value=mock_pos), \
             patch("app.scheduler.daily_wave_scheduler.get_armed_signal", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler._check_position_from_vps", return_value=False):
            run_daily_wave_job()
        summary = mock_send.call_args[0][0]
        assert "พบสัญญาณ: 0" in summary

    def test_ready_signal_sends_message(self):
        from app.scheduler.daily_wave_scheduler import run_daily_wave_job
        with patch("app.scheduler.daily_wave_scheduler.analyze_symbol", return_value=_make_analysis()), \
             patch("app.scheduler.daily_wave_scheduler.send_message") as mock_send, \
             patch("app.scheduler.daily_wave_scheduler.get_active", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler.get_armed_signal", return_value=None), \
             patch("app.scheduler.daily_wave_scheduler._check_position_from_vps", return_value=False), \
             patch("app.scheduler.daily_wave_scheduler.save_armed_signal"):
            run_daily_wave_job()
        assert mock_send.call_count >= 2  # signal + summary