"""
รัน backtest ทั้ง 50 เหรียญ แล้วสรุปผลละเอียด
Usage: python run_backtest_all.py
"""
import json
import sys
import os

# เพิ่ม path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.backtest.live_mirror_bt import run_symbol_bt

SYMBOLS = [
    "BTCUSDT","ETHUSDT","XRPUSDT","BNBUSDT","SOLUSDT",
    "ADAUSDT","DOGEUSDT","TRXUSDT","TONUSDT","LINKUSDT",
    "AVAXUSDT","DOTUSDT","LTCUSDT","NEARUSDT","UNIUSDT",
    "ICPUSDT","APTUSDT","ATOMUSDT","HBARUSDT","FILUSDT",
    "ARBUSDT","OPUSDT","SUIUSDT","INJUSDT","STXUSDT",
    "IMXUSDT","AAVEUSDT","GRTUSDT","RENDERUSDT","TIAUSDT",
    "POLUSDT","MKRUSDT","ALGOUSDT","LDOUSDT","VETUSDT",
    "SEIUSDT","TAOUSDT","FTMUSDT","KAVAUSDT","RUNEUSDT",
    "BEAMXUSDT","SANDUSDT","MANAUSDT","AXSUSDT","FLOWUSDT",
    "CHZUSDT","ENSUSDT","APEUSDT","QNTUSDT","EGLDUSDT",
]

results = []
errors  = []

print("=" * 60)
print("  BACKTEST REPORT — Elliott Wave System")
print("=" * 60)
print(f"{'Symbol':<14} {'n':>4} {'W':>4} {'L':>4} {'P1':>4} {'P2':>4} {'Full':>4} {'WR%':>7} {'R':>8} {'MaxDD':>7}")
print("-" * 60)

for sym in SYMBOLS:
    csv_path = f"data/{sym}_1d.csv"
    if not os.path.exists(csv_path):
        print(f"{sym:<14} {'NO CSV':>40}")
        errors.append(sym)
        continue

    try:
        import logging
        logging.disable(logging.CRITICAL)

        csv4h = f"data/{sym}_4h.csv"
        csv1w = f"data/{sym}_1w.csv"
        out = run_symbol_bt(
            sym,
            csv_path=csv_path,
            csv_path_4h=csv4h if os.path.exists(csv4h) else None,
            csv_path_1w=csv1w if os.path.exists(csv1w) else None,
        )

        logging.disable(logging.NOTSET)

        s = out.get("summary", {})
        n = s.get("n", 0)

        if n == 0:
            print(f"{sym:<14} {'n=0 (no trades)':>40}")
            continue

        wins     = s.get("wins", 0)
        losses   = s.get("losses", 0)
        wp1      = s.get("wins_p1", 0)
        wp2      = s.get("wins_p2", 0)
        wfull    = s.get("wins_full", 0)
        wr       = s.get("winrate", 0.0)
        total_r  = s.get("total_R", 0.0)
        max_dd   = s.get("max_dd_R", 0.0)

        r_str  = f"{total_r:+.2f}"
        dd_str = f"{max_dd:.2f}"

        print(f"{sym:<14} {n:>4} {wins:>4} {losses:>4} {wp1:>4} {wp2:>4} {wfull:>4} {wr:>6.1f}% {r_str:>8} {dd_str:>7}")

        results.append({
            "symbol":  sym,
            "n":       n,
            "wins":    wins,
            "losses":  losses,
            "wins_p1": wp1,
            "wins_p2": wp2,
            "wins_full": wfull,
            "winrate": wr,
            "total_R": total_r,
            "max_dd":  max_dd,
            "max_win_streak":  s.get("max_win_streak", 0),
            "max_loss_streak": s.get("max_loss_streak", 0),
        })

    except Exception as e:
        print(f"{sym:<14} ERROR: {e}")
        errors.append(sym)

# ─── สรุปรวม ───────────────────────────────────────────
print("=" * 60)

if not results:
    print("ไม่มีผล")
    sys.exit(0)

total_n     = sum(r["n"]       for r in results)
total_wins  = sum(r["wins"]    for r in results)
total_loss  = sum(r["losses"]  for r in results)
total_wp1   = sum(r["wins_p1"] for r in results)
total_wp2   = sum(r["wins_p2"] for r in results)
total_wfull = sum(r["wins_full"] for r in results)
total_R     = sum(r["total_R"] for r in results)
avg_wr      = sum(r["winrate"] for r in results) / len(results)
avg_dd      = sum(r["max_dd"]  for r in results) / len(results)

print(f"\nสรุปรวม:")
print(f"  เหรียญที่มีผล : {len(results)} เหรียญ")
print(f"  รวมไม้        : {total_n}")
print(f"  รวม Win       : {total_wins}  (Full={total_wfull}, P2={total_wp2}, P1={total_wp1})")
print(f"  รวม Loss      : {total_loss}")
print(f"  avg winrate   : {avg_wr:.2f}%")
print(f"  รวม R         : {total_R:+.2f}")
print(f"  avg MaxDD     : {avg_dd:.2f} R")

# ─── Top 5 ดีสุด ───────────────────────────────────────
print(f"\nTop 5 — winrate สูงสุด:")
top_wr = sorted(results, key=lambda x: -x["winrate"])[:5]
for r in top_wr:
    print(f"  {r['symbol']:<14} WR={r['winrate']:.1f}%  R={r['total_R']:+.2f}  n={r['n']}")

print(f"\nTop 5 — R สูงสุด:")
top_r = sorted(results, key=lambda x: -x["total_R"])[:5]
for r in top_r:
    print(f"  {r['symbol']:<14} R={r['total_R']:+.2f}  WR={r['winrate']:.1f}%  n={r['n']}")

# ─── Bottom 5 แย่สุด ───────────────────────────────────
print(f"\nBottom 5 — R ต่ำสุด:")
bot_r = sorted(results, key=lambda x: x["total_R"])[:5]
for r in bot_r:
    print(f"  {r['symbol']:<14} R={r['total_R']:+.2f}  WR={r['winrate']:.1f}%  n={r['n']}")

# ─── เหรียญขาดทุน ──────────────────────────────────────
losers = [r for r in results if r["total_R"] < 0]
print(f"\nเหรียญขาดทุน (R < 0): {len(losers)} เหรียญ")
for r in sorted(losers, key=lambda x: x["total_R"]):
    print(f"  {r['symbol']:<14} R={r['total_R']:+.2f}  WR={r['winrate']:.1f}%  n={r['n']}")

if errors:
    print(f"\nข้าม (ไม่มี CSV / error): {', '.join(errors)}")

print("=" * 60)

# บันทึก JSON
out_path = "backtest_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"บันทึกผลละเอียดไว้ที่: {out_path}")