import math
from app.trading.binance_trader import get_open_positions, set_stop_loss, set_take_profit

def main():
    pos = get_open_positions()
    if not pos:
        print("NO_OPEN_POSITION -> เปิด position ซักเหรียญก่อน แล้วค่อยเทส")
        return

    p = pos[0]
    symbol = p["symbol"]
    amt = float(p.get("positionAmt", 0) or 0)
    mark = float(p.get("markPrice", 0) or 0)

    if amt == 0 or mark <= 0:
        print("BAD_POSITION_DATA", p)
        return

    open_side = "BUY" if amt > 0 else "SELL"

    sl = mark * (0.50 if amt > 0 else 1.50)
    tp = mark * (1.50 if amt > 0 else 0.50)

    sl = float(f"{sl:.8f}")
    tp = float(f"{tp:.8f}")

    print("TEST_SYMBOL:", symbol, "amt:", amt, "mark:", mark, "open_side:", open_side)
    print("TRY_SL:", sl)
    print("TRY_TP:", tp)

    set_stop_loss(symbol, open_side, abs(amt), sl)
    set_take_profit(symbol, open_side, abs(amt), tp)

    print("OK: SL/TP attached via algoOrder")

if __name__ == "__main__":
    main()
