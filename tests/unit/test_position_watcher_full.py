from app.trading import position_watcher


def test_tp1_hit():
    position = {
        "entry": 100,
        "tp1": 105
    }

    price = 106
    assert price >= position["tp1"]


def test_sl_hit():
    position = {
        "entry": 100,
        "sl": 95
    }

    price = 94
    assert price <= position["sl"]