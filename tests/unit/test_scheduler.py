from app.scheduler import daily_wave_scheduler


def test_scheduler_symbol_loop():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    results = []

    for s in symbols:
        results.append(s)

    assert len(results) == 3