def simulate_position(position, price):

    if position["direction"] == "LONG":

        if price <= position["sl"]:
            return "SL"

        if price >= position["tp3"]:
            return "TP3"

        if price >= position["tp2"]:
            return "TP2"

        if price >= position["tp1"]:
            return "TP1"

    return "OPEN"


def test_position_tp1():

    pos = {
        "direction":"LONG",
        "entry":100,
        "sl":95,
        "tp1":105,
        "tp2":110,
        "tp3":115
    }

    result = simulate_position(pos,106)

    assert result == "TP1"


def test_position_sl():

    pos = {
        "direction":"LONG",
        "entry":100,
        "sl":95,
        "tp1":105,
        "tp2":110,
        "tp3":115
    }

    result = simulate_position(pos,94)

    assert result == "SL"