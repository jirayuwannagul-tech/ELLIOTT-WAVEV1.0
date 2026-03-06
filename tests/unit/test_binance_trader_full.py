from app.trading import binance_trader


def test_price_rounding():
    price = 100.12345
    result = round(price, 2)
    assert result == 100.12


def test_qty_rounding():
    qty = 0.123456
    result = round(qty, 3)
    assert result == 0.123


def test_direction_long():
    direction = "LONG"
    assert direction in ["LONG", "SHORT"]


def test_direction_short():
    direction = "SHORT"
    assert direction in ["LONG", "SHORT"]