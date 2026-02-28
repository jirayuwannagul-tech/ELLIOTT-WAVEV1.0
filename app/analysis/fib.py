def fib_retracement(start: float, end: float, current: float):
    move = end - start
    if move == 0:
        return None
    retrace = (current - end) / move

    # ถ้า retrace เกิน 1.0 = ราคากลับเกินจุดเริ่มต้น Wave1 → invalid
    if retrace > 1.0:
        return None

    # ถ้าติดลบ = ยังไม่ได้ retrace เลย → invalid
    if retrace < 0:
        return None

    return retrace

def fib_extension(a: float, b: float, c: float):
    """
    Calculate Fibonacci extension targets
    Wave A = a -> b
    Wave B = retrace to c
    """

    length = b - a

    targets = {
        "1.0": c + length,
        "1.618": c + (length * 1.618),
        "2.0": c + (length * 2.0),
    }

    return targets


def fib_zone_match(value: float):
    zones = {
        "0.236": 0.236,
        "0.382": 0.382,
        "0.5": 0.5,
        "0.618": 0.618,
        "0.786": 0.786,
        "1.0": 1.0,
        "1.618": 1.618,
    }

    tolerance = 0.03

    matches = []

    for name, level in zones.items():
        if abs(value - level) <= tolerance:
            matches.append(name)

    return matches  