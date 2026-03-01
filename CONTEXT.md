# CONTEXT — Elliott Wave Trading System
> อ่านไฟล์นี้ก่อนทำอะไรทุกครั้ง ห้ามข้าม

---

## ระบบนี้คืออะไร
บอทเทรด crypto อัตโนมัติบน Binance Futures
- วิเคราะห์รูปแบบ Elliott Wave จาก pivot points
- Timeframe หลัก: 1D
- 38 symbols
- ส่ง signal ผ่าน Telegram

---

## สถาปัตยกรรม Deployment

```
┌──────────────────────────────────────────────────────────────┐
│                           app/                               │
├──────────────────────────────────────────────────────────────┤
│ data/        → ดึง/ส่งออกข้อมูล (Binance → csv / sqlite)     │
│ indicators/  → คำนวณ EMA/RSI/ATR/Volume/Trend                │
│ analysis/    → สมอง: pivots→wave→scenarios→gates→trade_plan   │
│ risk/        → แผน SL/TP + RR gate (build_trade_plan)        │
│ scheduler/   → งานประจำวัน (run_daily / trend-watch)         │
│ services/    → ส่งออก (Telegram report)                       │
│ trading/     → ยิงออเดอร์จริง + ตั้ง SL/TP + watcher TP/SL    │
│ state/       → เก็บสถานะ positions.db (ACTIVE/CLOSED)         │
│ performance/ → dashboard /performance (R, DD, equity)          │
│ main.py      → Flask API + Dashboard + routes                 │
└──────────────────────────────────────────────────────────────┘

CSV/SQLite (data/)
   │
   ▼
Indicators (indicators/)
   │
   ▼
Wave Engine (analysis/) ──► Risk Plan (risk/)
   │                          │
   │                          ▼
   ├──► Scheduler (scheduler/) ──► Telegram (services/)
   │
   └──► /execute (main.py) ──► trade_executor (trading/)
                               │
                               ▼
                     Binance Futures (binance_trader)
                               │
                               ▼
                    positions.db (state/)
                               │
                               ▼
                  position_watcher (trading/)
                               │
                               ▼
                 performance dashboard (performance/)

Scheduler พบ READY
→ ส่งข้อความ
→ /execute รับ payload
→ trade_executor:
   - กันเปิดซ้ำ (get_active)
   - คำนวณ qty
   - เปิด market
   - ได้ fill จริง → คำนวณ SL/TP ใหม่
   - RR ต่ำ → emergency close
   - ตั้ง SL/TP (algoOrder)
   - lock_new_position ลง DB
→ position_watcher เฝ้า TP1/TP2/TP3/SL แล้วอัปเดต DB

```

### Flow การทำงาน
1. **VS Code** → แก้โค้ด → `git push` ไป GitHub
2. **GitHub** → trigger auto-deploy ไป Railway และ VPS พร้อมกัน

name: Deploy to VPS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: SSH Deploy
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          port: ${{ secrets.VPS_PORT }}
          script: |
            set -e

            echo "== CD PROJECT =="
            cd /root/ELLIOTT-WAVEV1.0

            echo "== GIT PULL =="
            git fetch origin
            git reset --hard origin/main

            echo "== INSTALL REQUIREMENTS =="
            pip3 install -r requirements.txt

            echo "== RESTART SERVICE =="
            systemctl restart elliott

            echo "== DONE =="

3. **Railway** → รัน `analyze_symbol()` ทุกเช้า 07:05 → ส่ง signal ผ่าน POST `/execute` ไป VPS
4. **VPS** → รับ signal → เรียก Binance Futures API (IP ของ VPS ถูก whitelist ไว้)
5. **Binance** → เปิด/ปิด position ตาม trade plan

### หมายเหตุสำคัญ
- Railway ใช้สำหรับ **วิเคราะห์และ schedule** เท่านั้น (ไม่แตะ Binance โดยตรง)
- VPS ใช้สำหรับ **execute order** เท่านั้น (รับคำสั่งจาก Railway)
- แก้โค้ดที่ VS Code แล้ว push → ทั้ง Railway และ VPS ได้โค้ดใหม่อัตโนมัติ
- `EXEC_TOKEN` ใช้ authenticate ระหว่าง Railway → VPS (ป้องกันคนอื่น call `/execute`)
- `VPS_URL` = URL ของ VPS ที่ Railway ใช้ส่ง signal ไป

---

## เป้าหมายของระบบ
สร้าง **edge** ในการเทรด — ได้สัญญาณที่มีคุณภาพ ไม่ใช่เยอะ ไม่ใช่น้อย แต่ **ถูกต้องตามหลัก Elliott Wave**

---

## โครงสร้างไฟล์สำคัญ
```
elliott-wave-system/
├── app/
│   ├── analysis/
│   │   ├── wave_engine.py        ← วิเคราะห์ signal LIVE (หัวใจหลัก)
│   │   ├── context_gate.py       ← กรอง confidence + macro bias
│   │   ├── macro_bias.py         ← คำนวณ allow_long/allow_short
│   │   ├── market_regime.py      ← ตรวจ TREND/RANGE/CHOP
│   │   ├── multi_tf.py           ← weekly permit + 4H confirm
│   │   ├── wave_scenarios.py     ← สร้าง ABC/IMPULSE scenarios
│   │   ├── wave_rules.py         ← validate_impulse / validate_abc
│   │   ├── wave_labeler.py       ← label wave degree
│   │   ├── pivot.py              ← หา pivot points
│   │   ├── fib.py                ← คำนวณ Fibonacci levels
│   │   ├── btc_cycle.py          ← BTC cycle bias
│   │   ├── trend_detector.py     ← ตรวจ trend direction
│   │   └── zones.py              ← support/resistance zones
│   ├── backtest/
│   │   ├── backtest_runner.py    ← ทดสอบย้อนหลัง
│   │   └── live_mirror_bt.py     ← backtest ที่ mirror filter ชุดเดียวกับ live
│   ├── config/
│   │   └── wave_settings.py      ← SYMBOLS, MIN_CONFIDENCE, MIN_RR
│   ├── data/
│   │   ├── binance_fetcher.py    ← ดึง OHLCV จาก Binance
│   │   └── export_ohlcv_csv.py   ← export ข้อมูลเป็น CSV
│   ├── indicators/
│   │   ├── trend_filter.py       ← allow_direction(), trend_filter_ema()
│   │   ├── atr.py                ← คำนวณ ATR
│   │   ├── ema.py                ← คำนวณ EMA
│   │   ├── rsi.py                ← คำนวณ RSI
│   │   └── volume.py             ← volume indicators
│   ├── performance/
│   │   ├── dashboard.py          ← /performance route
│   │   └── metrics.py            ← คำนวณ R, DD, equity
│   ├── risk/
│   │   └── risk_manager.py       ← build_trade_plan(), คำนวณ RR
│   ├── scheduler/
│   │   └── daily_wave_scheduler.py ← run_daily_wave_job, run_trend_watch_job
│   ├── services/
│   │   └── telegram_reporter.py  ← ส่ง signal ผ่าน Telegram
│   ├── state/
│   │   └── position_manager.py   ← positions.db (ACTIVE/CLOSED)
│   ├── trading/
│   │   ├── binance_trader.py     ← Binance Futures API wrapper
│   │   ├── position_sizer.py     ← คำนวณ qty จาก notional
│   │   ├── position_watcher.py   ← เฝ้า TP1/TP2/TP3/SL
│   │   └── trade_executor.py     ← execute order จริง
│   └── main.py                   ← Flask API + Dashboard + routes
├── data/                         ← CSV + SQLite (OHLCV ทุก symbol)
├── tests/
│   ├── test_pivot.py
│   ├── test_risk_plan.py
│   ├── test_wave_engine_smoke.py
│   └── test_wave_rules.py
├── tools/
│   ├── code_audit.py
│   └── update_top30_futures_1d1000.py
├── scripts/
│   └── test_attach_sl_tp.py
├── filter_test.py                ← สคริปต์ทดสอบตัวกรอง (สร้าง Feb 2026)
├── run_backtest_all.py           ← รัน backtest ทุก symbol
├── wave_status.py                ← ดู wave status ปัจจุบัน
├── debug_btc.py                  ← debug BTC signal
├── conftest.py
├── requirements.txt
├── Procfile
└── CONTEXT.md                    ← ไฟล์นี้

---

---

## การแก้ไขที่ทำไปแล้ว (Feb 2026)

### รอบที่ 1
| ไฟล์ | สิ่งที่แก้ | ผลที่คาดหวัง |
|------|-----------|-------------|
| `app/analysis/wave_engine.py` | ลบ `_force_minimal_trade_plan`, `_fallback_entry_from_pivots`, `_ensure_basic_risk_levels` | F_RR_VALID ทำงานจริง |
| `app/analysis/macro_bias.py` | threshold `>= 60` → `>= 50` | F_MACRO_BIAS block สวน trend ได้จริง |
| `app/risk/risk_manager.py` | แก้ `_safe_fib_extension` ใช้ `direction + base_len` แทน signed math | fib_extension ถูกทิศทุกกรณี รวมถึง fallback pivot |

### รอบที่ 2 (Mar 2026)
| ไฟล์ | สิ่งที่แก้ | ผลที่คาดหวัง |
|------|-----------|-------------|
| `app/state/position_manager.py` | `DB_PATH` เปลี่ยนจาก hardcode `/root/...` เป็น `Path(__file__).resolve().parents[2]` + รับ override ผ่าน `ELLIOTT_DB` ENV | รันบน Mac / VPS / Railway ได้โดยไม่ต้องตั้ง ENV |
| `app/analysis/pivot.py` | guard condition `len(df) < atr_length + right + left + 1` → `len(df) < left + right + 1` | `find_fractal_pivots` ไม่ return `[]` เมื่อข้อมูลน้อยกว่า 14 แถว |
| `app/config/wave_settings.py` | เพิ่ม `SOLUSDT: 8.0` ใน `NOTIONAL_MAP`, ลบ `AAEUSDT` ออก | SOL order ไม่ error minQty |
| `.env` | ลบ `ELLIOTT_DB=/root/ELLIOTT-WAVEV1.0/data/positions.db` ออก | ไม่ override DB_PATH ที่แก้ไปแล้ว |
---

## ปัญหาที่รอแก้ไข
- [ ] Live กับ Backtest ใช้ filter คนละชุด — backtest มี ATR compression, RSI midline, trend_direction ที่ live ไม่มี
- [ ] `backtest_runner.py` ควร mirror filter ชุดเดียวกับ live เพื่อให้ผลทดสอบสะท้อนความเป็นจริง

---

## กฎเหล็ก — AI ต้องทำตามทุกครั้ง
1. **อ่านโค้ดเก่าก่อนเสมอ** ก่อนแก้ไขอะไร
2. **ห้ามสร้างไฟล์ใหม่** ถ้าไฟล์เก่ามีอยู่แล้ว — แก้ของเก่าแทน
3. **แก้ทีละจุด** ระบุชัดว่าแก้ฟังก์ชันอะไร บรรทัดไหน
4. **ห้ามเปลี่ยน logic หลัก** โดยไม่ถามก่อน
5. **บอกผลที่คาดว่าจะเกิด** ก่อนแก้ทุกครั้ง
6. **ถ้าไม่แน่ใจ ถามก่อน** อย่าเดาแล้วเขียนทับ

---

## สิ่งที่ห้ามทำ
- ❌ สร้าง wave_engine ใหม่
- ❌ สร้าง backtest_runner ใหม่
- ❌ เปลี่ยน Elliott Wave logic โดยไม่ถาม
- ❌ แก้หลายไฟล์พร้อมกัน
- ❌ เพิ่ม filter ใหม่โดยไม่ถาม