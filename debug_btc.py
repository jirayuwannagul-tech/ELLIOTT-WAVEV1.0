import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from app.indicators.atr import add_atr
from app.analysis.pivot import find_fractal_pivots, filter_pivots
from app.analysis.wave_scenarios import _find_major_structure, _determine_wave_position, build_scenarios

df = pd.read_csv("data/BTCUSDT_1d.csv")
df = add_atr(df, length=14)

pivots = find_fractal_pivots(df)
pivots = filter_pivots(pivots, min_pct_move=1.5)

print(f"pivots พบ: {len(pivots)} จุด")
print(f"5 ตัวล่าสุด: {[(p['type'], p['price'], p.get('degree')) for p in pivots[-5:]]}")

structure = _find_major_structure(pivots)
print(f"\nmajor_trend: {structure.get('major_trend')}")
print(f"intermediate pivots: {len(structure.get('intermediate_pivots', []))}")

wave_pos = _determine_wave_position(pivots, structure)
print(f"\nwave position: {wave_pos.get('position')}")
print(f"entry_type: {wave_pos.get('entry_type')}")
print(f"fib_ratio: {wave_pos.get('fib_ratio')}")