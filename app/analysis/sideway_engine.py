# app/analysis/sideway_engine.py
from typing import Dict
import pandas as pd

def run_sideway_engine(symbol: str, df: pd.DataFrame, base: Dict) -> Dict:
    """
    SIDEWAY mode: ไม่สร้างสัญญาณเทรด
    แค่สรุปว่า range ประมาณไหน + โหมดนี้ลดขนาดไม้
    """
    high20 = float(df["high"].tail(20).max())
    low20 = float(df["low"].tail(20).min())
    close = float(df["close"].iloc[-1])

    base.update({
        "mode": "SIDEWAY",
        "sideway": {
            "range_low_20": low20,
            "range_high_20": high20,
            "mid": (low20 + high20) / 2.0,
            "note": "SIDEWAY: เก็บข้อมูลคลื่น/เรนจ์เท่านั้น ไม่ยิงสัญญาณ",
        },
        "message": f"SIDEWAY: range(20) {low20:,.2f} - {high20:,.2f} | close={close:,.2f}",
        "scenarios": [],
    })
    return base