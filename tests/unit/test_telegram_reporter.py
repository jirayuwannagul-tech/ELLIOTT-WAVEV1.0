# tests/unit/test_telegram_reporter.py
import pytest
import os
from unittest.mock import patch, MagicMock
from app.services.telegram_reporter import _tg_api_url, _fmt_price, format_symbol_report, send_message


def _make_analysis(symbol="BTCUSDT", direction="SHORT", entry=100.0, sl=110.0,
                   tp1=90.0, tp2=80.0, tp3=70.0, support=85.0, resist=115.0):
    return {
        "symbol": symbol,
        "position_size_mult": 1.0,
        "scenarios": [{
            "direction": direction,
            "trade_plan": {
                "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
            }
        }],
        "sr": {
            "support": {"level": support},
            "resist":  {"level": resist},
        }
    }


class TestTgApiUrl:
    def test_format(self):
        url = _tg_api_url("sendMessage", "TOKEN123")
        assert url == "https://api.telegram.org/botTOKEN123/sendMessage"


class TestFmtPrice:
    def test_above_1(self):
        assert _fmt_price(1234.5) == "1,234.50"

    def test_below_1(self):
        assert "0.50000" in _fmt_price(0.5)

    def test_returns_string(self):
        assert isinstance(_fmt_price(100.0), str)


class TestFormatSymbolReport:
    def test_no_scenarios_returns_no_signal(self):
        analysis = {"symbol": "BTCUSDT", "scenarios": []}
        result = format_symbol_report(analysis)
        assert "ไม่มีสัญญาณ" in result

    def test_contains_symbol(self):
        result = format_symbol_report(_make_analysis("ETHUSDT"))
        assert "ETHUSDT" in result

    def test_contains_direction(self):
        result = format_symbol_report(_make_analysis(direction="SHORT"))
        assert "SHORT" in result

    def test_contains_entry(self):
        result = format_symbol_report(_make_analysis(entry=69000.0))
        assert "69,000.00" in result

    def test_contains_timestamp(self):
        result = format_symbol_report(_make_analysis())
        assert "📅" in result

    def test_contains_elliott_wave(self):
        result = format_symbol_report(_make_analysis())
        assert "ELLIOTT-WAVE" in result

    def test_none_entry_shows_dash(self):
        analysis = _make_analysis()
        analysis["scenarios"][0]["trade_plan"]["entry"] = None
        result = format_symbol_report(analysis)
        assert "Entry: -" in result


class TestSendMessage:
    def test_no_token_prints_preview(self, capsys):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            send_message("test message")
        captured = capsys.readouterr()
        assert "TELEGRAM PREVIEW" in captured.out
        assert "test message" in captured.out

    def test_sends_with_token(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "TOKEN", "TELEGRAM_CHAT_ID": "123"}), \
             patch("app.services.telegram_reporter.requests.post", return_value=mock_resp) as mock_post:
            send_message("hello")
        mock_post.assert_called_once()

    def test_topic_id_added_to_payload(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "TOKEN", "TELEGRAM_CHAT_ID": "123"}), \
             patch("app.services.telegram_reporter.requests.post", return_value=mock_resp) as mock_post:
            send_message("hello", topic_id=42)
        payload = mock_post.call_args[1]["json"]
        assert payload["message_thread_id"] == 42