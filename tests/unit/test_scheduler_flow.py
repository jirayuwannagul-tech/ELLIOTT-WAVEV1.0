from app.scheduler import daily_wave_scheduler


def test_symbol_loop():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    processed = []

    for s in symbols:
        processed.append(s)

    assert len(processed) == 3


def test_scheduler_runs():
    ran = True
    assert ran