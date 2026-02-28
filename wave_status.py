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

structure = _find_major_structure(pivots)
wave_pos  = _determine_wave_position(pivots, structure)
scenarios = build_scenarios(pivots, macro_trend="BULL", rsi14=50.0)

print("=" * 50)
print("  BTC WAVE ANALYSIS")
print("=" * 50)
print(f"Major Trend   : {structure.get('major_trend')}")
print(f"Wave Position : {wave_pos.get('position')}")
print(f"Direction     : {wave_pos.get('direction')}")
print(f"Entry Type    : {wave_pos.get('entry_type')}")
print(f"Note          : {wave_pos.get('note')}")
print(f"Fib Ratio     : {wave_pos.get('fib_ratio')}")
print()

recent_high = structure.get("recent_high")
recent_low  = structure.get("recent_low")
if recent_high and recent_low:
    print(f"Recent High   : {recent_high['price']:,.2f}")
    print(f"Recent Low    : {recent_low['price']:,.2f}")

print()
print(f"Scenarios พบ  : {len(scenarios)}")
for sc in scenarios:
    print(f"  - {sc['type']} | score={sc['score']:.1f} | conf={sc['confidence']:.1f}")
    for r in sc.get('reasons', []):
        print(f"    → {r}")
print("=" * 50)