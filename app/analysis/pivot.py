import pandas as pd


def find_fractal_pivots(df: pd.DataFrame, left: int = 2, right: int = 2):
    """
    Detect fractal pivots (2-2 by default)
    Returns list of dict:
    {
        "index": int,
        "price": float,
        "type": "H" or "L"
    }

    หมายเหตุ: แต่ละแท่งได้ pivot ได้แค่ 1 ประเภท (H หรือ L)
    ถ้าเป็นได้ทั้งคู่ (เช่น doji ใหญ่) → เลือกฝั่งที่ move ห่างจาก prev_close มากกว่า
    """

    pivots = []

    for i in range(left, len(df) - right):
        high_slice = df["high"].iloc[i - left : i + right + 1]
        low_slice = df["low"].iloc[i - left : i + right + 1]

        current_high = float(df["high"].iloc[i])
        current_low = float(df["low"].iloc[i])

        is_pivot_high = current_high == high_slice.max()
        is_pivot_low = current_low == low_slice.min()

        # ✅ กัน H+L บนแท่งเดียวกัน
        # ถ้าเป็นได้ทั้งคู่ → เลือกฝั่งที่ move ห่างจาก prev_close มากกว่า
        if is_pivot_high and is_pivot_low:
            prev_close = float(df["close"].iloc[i - 1])
            high_move = abs(current_high - prev_close)
            low_move = abs(current_low - prev_close)

            if high_move >= low_move:
                is_pivot_low = False   # เลือก H
            else:
                is_pivot_high = False  # เลือก L

        if is_pivot_high:
            pivots.append(
                {
                    "index": i,
                    "price": current_high,
                    "type": "H",
                }
            )
        elif is_pivot_low:
            pivots.append(
                {
                    "index": i,
                    "price": current_low,
                    "type": "L",
                }
            )

    return pivots


def filter_pivots(pivots, min_pct_move: float = 0.5):
    """
    Remove small noisy pivots
    min_pct_move = minimum % difference between pivots
    """

    if not pivots:
        return []

    filtered = [pivots[0]]

    for pivot in pivots[1:]:
        last = filtered[-1]

        move_pct = abs((pivot["price"] - last["price"]) / last["price"]) * 100

        if move_pct >= min_pct_move:
            filtered.append(pivot)

    return filtered