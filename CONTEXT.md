# CONTEXT — Elliott Wave Trading System
> อ่านไฟล์นี้ก่อนทำอะไรทุกครั้ง ห้ามข้าม

---

## ระบบนี้คืออะไร
บอทเทรด crypto อัตโนมัติบน Binance Futures
- วิเคราะห์รูปแบบ Elliott Wave จาก pivot points
- Timeframe หลัก: 1D
- 23 symbols
- ส่ง signal ผ่าน Telegram

---

## สถาปัตยกรรม Deployment

```
VS Code (local)
    │
    │  git push
    ▼
GitHub (repo)
    │
    │  auto-deploy (push trigger)
    ├──────────────────────────────▶ Railway
    │                                  │  วิเคราะห์ Elliott Wave
    │                                  │  คำนวณ signal
    │                                  │  ส่ง /execute ไป VPS
    │                                  │  (Railway ไม่มี whitelist IP
    │                                  │   จึงส่งตรง Binance ไม่ได้)
    │                                  │
    │                                  ▼
    └──────────────────────────────▶ VPS (whitelist IP)
                                       │  รับ signal จาก Railway
                                       │  เปิด/ปิด position บน Binance Futures
                                       ▼
                                   Binance Futures API
```

### Flow การทำงาน
1. **VS Code** → แก้โค้ด → `git push` ไป GitHub
2. **GitHub** → trigger auto-deploy ไป Railway และ VPS พร้อมกัน
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
│   │   └── pivot.py              ← หา pivot points
│   ├── backtest/
│   │   └── backtest_runner.py    ← ทดสอบย้อนหลัง
│   ├── indicators/
│   │   └── trend_filter.py       ← allow_direction(), trend_filter_ema()
│   ├── risk/
│   │   └── risk_manager.py       ← build_trade_plan(), คำนวณ RR
│   └── config/
│       └── wave_settings.py      ← SYMBOLS, MIN_CONFIDENCE, MIN_RR
├── filter_test.py                ← สคริปต์ทดสอบตัวกรอง (สร้าง Feb 2026)
└── CONTEXT.md                    ← ไฟล์นี้
```

---

## Filter ทั้งหมด 12 ตัว

| ID | ชื่อ | ไฟล์ | Live | Backtest | ประเภท |
|----|------|------|------|----------|--------|
| 1 | data_length | wave_engine.py | ✅ | ✅ | HARD |
| 2 | sideway_split | trend_detector.py | ✅ | ❌ | REDIRECT |
| 3 | pivot_count | wave_engine.py | ✅ | ✅ | HARD |
| 4 | min_confidence | context_gate.py | ✅ | ✅ | HARD |
| 5 | macro_bias_direction | context_gate.py | ✅ | ✅ | HARD |
| 6 | weekly_permit | multi_tf.py | ✅ | ❌ | HARD |
| 7 | h4_confirm | multi_tf.py | ✅ | ❌ | SOFT |
| 8 | rr_valid | risk_manager.py | ✅ | ✅ | HARD |
| 9 | trigger_price | wave_engine.py | ✅ | ✅ | HARD |
| 10 | atr_compression | backtest_runner.py | ❌ | ✅ | HARD |
| 11 | trend_direction | trend_filter.py | ❌ | ✅ | HARD |
| 12 | rsi_midline | backtest_runner.py | ❌ | ✅ | HARD |

---

## ผลทดสอบ filter_test.py (Feb 2026)
Baseline: 3 symbols (BTC, DOGE, TIA), 42 trades, winrate 30%

| Filter ปิด | trades | diff | winrate |
|---|---|---|---|
| F_ATR_COMPRESSION | 46 | +4 | 23% ↓ |
| F_TREND_DIRECTION | 42 | 0 | 30% = |
| F_RSI_MIDLINE | 48 | +6 | 28% ↓ |
| F_MIN_CONFIDENCE | 74 | +32 | 22% ↓ |
| F_MACRO_BIAS | 42 | 0 | 30% = |
| F_RR_VALID | 42 | 0 | 30% = |
| F_TRIGGER_PRICE | 43 | +1 | 29% ↓ |

**พบว่า:** F_TREND_DIRECTION, F_MACRO_BIAS, F_RR_VALID ปิดแล้วไม่มีผล → สาเหตุที่พบและแก้ไขแล้ว (Feb 2026):
- F_MACRO_BIAS: threshold `strength >= 60` สูงเกิน → แก้เป็น `>= 50` แล้ว
- F_RR_VALID: `_force_minimal_trade_plan` bypass valid=True → ลบออกแล้ว
- F_TREND_DIRECTION: อยู่ใน backtest_runner.py เท่านั้น ไม่มีใน live → รอแก้รอบถัดไป

---

## การแก้ไขที่ทำไปแล้ว (Feb 2026)

### รอบที่ 1
| ไฟล์ | สิ่งที่แก้ | ผลที่คาดหวัง |
|------|-----------|-------------|
| `app/analysis/wave_engine.py` | ลบ `_force_minimal_trade_plan`, `_fallback_entry_from_pivots`, `_ensure_basic_risk_levels` | F_RR_VALID ทำงานจริง |
| `app/analysis/macro_bias.py` | threshold `>= 60` → `>= 50` | F_MACRO_BIAS block สวน trend ได้จริง |
| `app/risk/risk_manager.py` | แก้ `_safe_fib_extension` ใช้ `direction + base_len` แทน signed math | fib_extension ถูกทิศทุกกรณี รวมถึง fallback pivot |

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