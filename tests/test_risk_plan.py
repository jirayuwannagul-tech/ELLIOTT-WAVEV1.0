from app.risk.risk_manager import build_trade_plan, calculate_rr

def _impulse_long(swing_low=92.0, swing_high=150.0):
    return {
        "type": "IMPULSE_LONG",
        "direction": "LONG",
        "swing_high": swing_high,
        "swing_low": swing_low,
        "pivots": [
            {"price": swing_low,  "type": "L"},
            {"price": swing_high, "type": "H"},
        ],
    }

def _impulse_short(swing_low=80.0, swing_high=128.0):
    return {
        "type": "IMPULSE_SHORT",
        "direction": "SHORT",
        "swing_high": swing_high,
        "swing_low": swing_low,
        "pivots": [
            {"price": swing_high, "type": "H"},
            {"price": swing_low,  "type": "L"},
        ],
    }

def _abc_up():
    return {
        "type": "ABC_UP",
        "direction": "LONG",
        "pivots": [
            {"price": 80.0,  "type": "L"},
            {"price": 150.0, "type": "H"},
            {"price": 100.0, "type": "L"},
            {"price": 180.0, "type": "H"},
        ],
    }

def _abc_down():
    return {
        "type": "ABC_DOWN",
        "direction": "SHORT",
        "pivots": [
            {"price": 150.0, "type": "H"},
            {"price": 100.0, "type": "L"},  # a_len=50 (ลดจาก 70)
            {"price": 120.0, "type": "H"},
            {"price": 50.0,  "type": "L"},
        ],
    }

# ─────────────────────────────────────────────
# IMPULSE LONG
# ─────────────────────────────────────────────

class TestImpulseLong:
    def test_valid_plan(self):
        """plan ถูกต้อง RR ผ่าน"""
        plan = build_trade_plan(_impulse_long(), current_price=100.0, min_rr=1.5)
        assert plan["valid"] is True
        assert plan["entry"] == 100.0
        assert plan["sl"] == 92.0
        assert plan["tp1"] > plan["entry"]
        assert plan["tp2"] > plan["tp1"]
        assert plan["tp3"] > plan["tp2"]

    def test_rr_meets_minimum(self):
        """RR ต้องผ่าน min_rr"""
        plan = build_trade_plan(_impulse_long(), current_price=100.0, min_rr=1.5)
        rr = calculate_rr(plan["entry"], plan["sl"], plan["tp2"])
        assert rr >= 1.5

    def test_sl_too_close_rejected(self):
        """SL ห่างน้อยกว่า 1% → invalid"""
        sc = _impulse_long(swing_low=99.5, swing_high=150.0)
        plan = build_trade_plan(sc, current_price=100.0, min_rr=1.5)
        assert plan["valid"] is False
        assert "ใกล้เกิน" in plan["reason"]

    def test_sl_too_far_rejected(self):
        """SL ห่างมากกว่า 10% → invalid"""
        sc = _impulse_long(swing_low=50.0, swing_high=150.0)
        plan = build_trade_plan(sc, current_price=100.0, min_rr=1.5)
        assert plan["valid"] is False
        assert "ไกลเกิน" in plan["reason"]

    def test_entry_below_sl_rejected(self):
        """entry ต่ำกว่า SL → invalid"""
        sc = _impulse_long(swing_low=105.0, swing_high=150.0)
        plan = build_trade_plan(sc, current_price=100.0, min_rr=1.5)
        assert plan["valid"] is False

# ─────────────────────────────────────────────
# IMPULSE SHORT
# ─────────────────────────────────────────────

class TestImpulseShort:
    def test_valid_plan(self):
        """plan short ถูกต้อง"""
        plan = build_trade_plan(_impulse_short(), current_price=120.0, min_rr=1.5)
        assert plan["valid"] is True
        assert plan["sl"] > plan["entry"]
        assert plan["tp1"] < plan["entry"]
        assert plan["tp2"] < plan["tp1"]
        assert plan["tp3"] < plan["tp2"]

    def test_rr_meets_minimum(self):
        """RR short ต้องผ่าน min_rr"""
        plan = build_trade_plan(_impulse_short(), current_price=120.0, min_rr=1.5)
        rr = calculate_rr(plan["entry"], plan["sl"], plan["tp2"])
        assert rr >= 1.5

# ─────────────────────────────────────────────
# ABC UP
# ─────────────────────────────────────────────

class TestABCUp:
    def test_valid_plan(self):
        """ABC UP plan ถูกต้อง"""
        plan = build_trade_plan(_abc_up(), current_price=110.0, min_rr=1.5)
        assert plan["valid"] is True
        assert plan["sl"] == 100.0   # l2 = pivot[2]
        assert plan["tp1"] > plan["entry"]

    def test_price_below_sl_rejected(self):
        """ราคาต่ำกว่า SL แล้ว → invalid"""
        plan = build_trade_plan(_abc_up(), current_price=95.0, min_rr=1.5)
        assert plan["valid"] is False
        assert "SL" in plan["reason"]

# ─────────────────────────────────────────────
# ABC DOWN
# ─────────────────────────────────────────────

class TestABCDown:
    def test_valid_plan(self):
        """ABC DOWN plan ถูกต้อง"""
        plan = build_trade_plan(_abc_down(), current_price=110.0, min_rr=1.5)
        assert plan["valid"] is True
        assert plan["sl"] == 120.0   # h2 = pivot[2]
        assert plan["tp1"] < plan["entry"]

    def test_price_above_sl_rejected(self):
        """ราคาสูงกว่า SL แล้ว → invalid"""
        plan = build_trade_plan(_abc_down(), current_price=125.0, min_rr=1.5)
        assert plan["valid"] is False
        assert "SL" in plan["reason"]

# ─────────────────────────────────────────────
# CALCULATE_RR
# ─────────────────────────────────────────────

class TestCalculateRR:
    def test_basic_rr(self):
        """entry=100 sl=90 tp=120 → RR=2.0"""
        rr = calculate_rr(100.0, 90.0, 120.0)
        assert abs(rr - 2.0) < 0.01

    def test_zero_risk(self):
        """entry == sl → RR=0"""
        rr = calculate_rr(100.0, 100.0, 120.0)
        assert rr == 0.0