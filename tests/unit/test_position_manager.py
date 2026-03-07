# tests/unit/test_position_manager.py
import pytest
import os
import tempfile
from unittest.mock import patch


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    db = tmp_path / "test_positions.db"
    with patch.dict(os.environ, {"ELLIOTT_DB": str(db)}):
        # re-import เพื่อให้ใช้ DB ใหม่
        import importlib
        import app.state.position_manager as pm
        importlib.reload(pm)
        yield pm


def _trade_plan():
    return {
        "entry": 100.0, "sl": 90.0,
        "tp1": 110.0, "tp2": 120.0, "tp3": 130.0,
        "qty": 1.0,
    }


class TestLockNewPosition:
    def test_lock_success(self, tmp_db):
        result = tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        assert result is True

    def test_lock_duplicate_returns_false(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        result = tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        assert result is False

    def test_lock_stores_active_status(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        pos = tmp_db.get_active("BTCUSDT", "1d")
        assert pos is not None
        assert pos.status == "ACTIVE"

    def test_lock_stores_correct_direction(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "SHORT", _trade_plan())
        pos = tmp_db.get_active("BTCUSDT", "1d")
        assert pos.direction == "SHORT"


class TestGetActive:
    def test_no_position_returns_none(self, tmp_db):
        assert tmp_db.get_active("ETHUSDT", "1d") is None

    def test_active_position_returned(self, tmp_db):
        tmp_db.lock_new_position("ETHUSDT", "1d", "LONG", _trade_plan())
        pos = tmp_db.get_active("ETHUSDT", "1d")
        assert pos is not None

    def test_closed_position_returns_none(self, tmp_db):
        tmp_db.lock_new_position("ETHUSDT", "1d", "LONG", _trade_plan())
        tmp_db.update_from_price("ETHUSDT", "1d", 85.0)  # โดน SL
        pos = tmp_db.get_active("ETHUSDT", "1d")
        assert pos is None


class TestUpdateFromPrice:
    def test_long_tp1_hit(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        pos, events = tmp_db.update_from_price("BTCUSDT", "1d", 115.0)
        assert events["tp1"] is True

    def test_long_sl_closes_position(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        pos, events = tmp_db.update_from_price("BTCUSDT", "1d", 85.0)
        assert events["sl"] is True
        assert events["closed"] is True
        assert pos.status == "CLOSED"

    def test_long_tp3_closes_position(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "LONG", _trade_plan())
        pos, events = tmp_db.update_from_price("BTCUSDT", "1d", 135.0)
        assert events["closed"] is True
        assert pos.closed_reason == "TP3"

    def test_short_sl_closes_position(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "SHORT", _trade_plan())
        pos, events = tmp_db.update_from_price("BTCUSDT", "1d", 115.0)
        assert events["sl"] is True
        assert pos.status == "CLOSED"

    def test_short_tp1_hit(self, tmp_db):
        tmp_db.lock_new_position("BTCUSDT", "1d", "SHORT", _trade_plan())
        pos, events = tmp_db.update_from_price("BTCUSDT", "1d", 105.0)
        assert events["tp1"] is True

    def test_no_position_returns_none(self, tmp_db):
        pos, events = tmp_db.update_from_price("MISSING", "1d", 100.0)
        assert pos is None
        assert events == {}


class TestArmedSignal:
    def test_save_and_get(self, tmp_db):
        tmp_db.save_armed_signal("BTCUSDT", "1d", "LONG", 100.0, _trade_plan())
        result = tmp_db.get_armed_signal("BTCUSDT", "1d")
        assert result is not None
        assert result["status"] == "ARMED"

    def test_clear_armed(self, tmp_db):
        tmp_db.save_armed_signal("BTCUSDT", "1d", "LONG", 100.0, _trade_plan())
        tmp_db.clear_armed_signal("BTCUSDT", "1d")
        assert tmp_db.get_armed_signal("BTCUSDT", "1d") is None

    def test_list_armed(self, tmp_db):
        tmp_db.save_armed_signal("BTCUSDT", "1d", "LONG", 100.0, _trade_plan())
        tmp_db.save_armed_signal("ETHUSDT", "1d", "SHORT", 200.0, _trade_plan())
        result = tmp_db.list_armed_signals("1d")
        assert len(result) == 2