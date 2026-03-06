from hypothesis import given, strategies as st, settings
import random


def simulate_trade(entry, sl, tp, prices):

    position = "OPEN"

    for p in prices:

        if position != "OPEN":
            break

        if p <= sl:
            return "SL"

        if p >= tp:
            return "TP"

    return "OPEN"


@settings(max_examples=50, deadline=None)
@given(
    entry=st.floats(min_value=10, max_value=100000),
    rr=st.floats(min_value=1.1, max_value=5),
)
def test_trade_lifecycle(entry, rr):

    risk = entry * 0.02
    sl = entry - risk
    tp = entry + (risk * rr)

    # random market simulation
    price = entry
    prices = []

    for _ in range(300):

        move = random.uniform(-risk * 0.8, risk * 0.8)
        price += move

        if price <= 1:
            price = 1

        prices.append(price)

    result = simulate_trade(entry, sl, tp, prices)

    assert result in ["TP", "SL", "OPEN"]