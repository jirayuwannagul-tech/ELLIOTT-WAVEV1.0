import pandas as pd

from app.analysis.pivot import find_fractal_pivots, filter_pivots


def test_find_fractal_pivots_basic():
    """
    สร้างข้อมูลราคาง่าย ๆ ที่มีจุดสูงต่ำชัดเจน
    แล้วเช็คว่า pivot ถูก detect จริง
    """

    data = {
        "open":  [1, 2, 3, 4, 5, 4, 3, 2, 1],
        "high":  [1, 2, 3, 4, 5, 4, 3, 2, 1],
        "low":   [1, 2, 3, 4, 5, 4, 3, 2, 1],
        "close": [1, 2, 3, 4, 5, 4, 3, 2, 1],
        "volume": [1]*9,
        "atr14":  [0.5] * 9,
    }

    df = pd.DataFrame(data)

    pivots = find_fractal_pivots(df)

    # ต้องมี pivot อย่างน้อย 1 จุด (ยอดบน)
    assert len(pivots) > 0

    # เช็คว่ามี type H อย่างน้อย 1 จุด
    types = [p["type"] for p in pivots]
    assert "H" in types


def test_filter_pivots_min_pct_move():
    """
    เช็คว่า filter_pivots กรองตาม % move จริง
    """

    pivots = [
        {"index": 0, "type": "L", "price": 100},
        {"index": 1, "type": "H", "price": 101},  # move 1%
        {"index": 2, "type": "L", "price": 100.5},  # move เล็ก
    ]

    # กำหนด min_pct_move = 2% → ควรเหลือน้อยลง
    filtered = filter_pivots(pivots, min_pct_move=2.0)

    # ต้องถูกกรองออกอย่างน้อย 1 จุด
    assert len(filtered) < len(pivots)