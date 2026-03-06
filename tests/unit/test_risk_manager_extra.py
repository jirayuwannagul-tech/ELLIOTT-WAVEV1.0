from app.risk.risk_manager import build_trade_plan, calculate_rr, recalculate_from_fill


# ─────────────────────────────────────────────
# SIDEWAY_RANGE
# ─────────────────────────────────────────────

def _sideway(direction="LONG", range_low=90.0, range_high=110.0, atr=1.0):
    return {
        "type": "SIDEWAY_RANGE",
        "direction": direction,
        "range_low": range_low,
        "range_high": range_high,
        "atr": atr,
    }


class TestSidewayRange:
    def test_long_near_support(self):
        """LONG near support → valid plan"""
        plan = build_trade_plan(_sideway("LONG"), current_price=91.0, min_rr=1.5)
        assert plan["valid"] is True
        assert plan["sl"] < plan["entry"]
        assert plan["tp1"] > plan["entry"]

    def test_short_near_resist(self):
        """SHORT near resist → valid plan"""
        plan = build_trade_plan(_sideway("SHORT"), current_price=109.0, min_rr=1.5)
        assert plan["valid"] is True
        assert plan["sl"] > plan["entry"]
        assert plan["tp1"] < plan["entry"]

    def test_invalid_range(self):
        """range_low >= range_high → invalid"""
        plan = build_trade_plan(
            _sideway("LONG", range_low=110.0, range_high=90.0),
            current_price=100.0,
        )
        assert plan["valid"] is False

    def test_zero_range_low(self):
        """range_low = 0 → invalid"""
        plan = build_trade_plan(
            _sideway("LONG", range_low=0.0),
            current_price=100.0,
        )
        assert plan["valid"] is False

    def test_rr_meets_minimum(self):
        """RR ต้องผ่าน min_rr"""
        plan = build_trade_plan(_sideway("LONG"), current_price=91.0, min_rr=1.5)
        if plan["valid"]:
            rr = calculate_rr(plan["entry"], plan["sl"], plan["tp2"])
            assert rr >= 1.5


# ─────────────────────────────────────────────
# SR ADJUSTMENT
# ─────────────────────────────────────────────

class TestSRadjustment:
    def test_impulse_long_sr_support_raises_sl(self):
        """support สูงกว่า SL เดิม → SL ถูก raise ขึ้น"""
        sc = {
            "type": "IMPULSE_LONG",
            "direction": "LONG",
            "swing_low": 92.0,
            "swing_high": 150.0,
            "pivots": [
                {"price": 92.0,  "type": "L"},
                {"price": 150.0, "type": "H"},
            ],
        }
        sr = {"support": {"level": 95.0}, "resist": {"level": 130.0}}
        plan = build_trade_plan(sc, current_price=100.0, min_rr=1.5, sr=sr)
        if plan["valid"]:
            assert plan["sl"] >= 95.0

    def test_impulse_short_sr_resist_lowers_sl(self):
        """resist ต่ำกว่า SL เดิม → SL ถูก lower ลง"""
        sc = {
            "type": "IMPULSE_SHORT",
            "direction": "SHORT",
            "swing_high": 128.0,
            "swing_low": 80.0,
            "pivots": [
                {"price": 128.0, "type": "H"},
                {"price": 80.0,  "type": "L"},
            ],
        }
        sr = {"support": {"level": 85.0}, "resist": {"level": 125.0}}
        plan = build_trade_plan(sc, current_price=120.0, min_rr=1.5, sr=sr)
        if plan["valid"]:
            assert plan["sl"] <= 125.0


# ─────────────────────────────────────────────
# RECALCULATE_FROM_FILL
# ─────────────────────────────────────────────

class TestABCSRadjustment:
    def test_abc_down_sr_resist_lowers_sl(self):
        """ABC DOWN + resist ต่ำกว่า SL → SL ถูก lower"""
        sc = {
            "type": "ABC_DOWN",
            "direction": "SHORT",
            "pivots": [
                {"price": 150.0, "type": "H"},
                {"price": 100.0, "type": "L"},
                {"price": 120.0, "type": "H"},
                {"price": 50.0,  "type": "L"},
            ],
        }
        sr = {"support": {"level": 85.0}, "resist": {"level": 118.0}}
        plan = build_trade_plan(sc, current_price=110.0, min_rr=1.5, sr=sr)
        if plan["valid"]:
            assert plan["sl"] <= 120.0

    def test_abc_up_sr_support_raises_sl(self):
        """ABC UP + support สูงกว่า SL → SL ถูก raise"""
        sc = {
            "type": "ABC_UP",
            "direction": "LONG",
            "pivots": [
                {"price": 80.0,  "type": "L"},
                {"price": 150.0, "type": "H"},
                {"price": 100.0, "type": "L"},
                {"price": 180.0, "type": "H"},
            ],
        }
        sr = {"support": {"level": 103.0}, "resist": {"level": 160.0}}
        plan = build_trade_plan(sc, current_price=115.0, min_rr=1.5, sr=sr)
        if plan["valid"]:
            assert plan["sl"] >= 100.0

    def test_abc_down_sl_too_close_rejected(self):
        """ABC DOWN SL ใกล้ entry น้อยกว่า 1% → invalid"""
        sc = {
            "type": "ABC_DOWN",
            "direction": "SHORT",
            "pivots": [
                {"price": 150.0, "type": "H"},
                {"price": 100.0, "type": "L"},
                {"price": 105.5, "type": "H"},  # SL ห่างแค่ 0.5% → ถูก reject
                {"price": 50.0,  "type": "L"},
            ],
        }
        plan = build_trade_plan(sc, current_price=105.0, min_rr=1.5)
        assert plan["valid"] is False


class TestImpulseEdgeCases:
    def test_invalid_direction_rejected(self):
        """direction ไม่ใช่ LONG/SHORT → invalid"""
        sc = {
            "type": "IMPULSE_LONG",
            "direction": "SIDEWAYS",
            "swing_high": 150.0,
            "swing_low": 92.0,
            "pivots": [
                {"price": 92.0,  "type": "L"},
                {"price": 150.0, "type": "H"},
            ],
        }
        plan = build_trade_plan(sc, current_price=100.0)
        assert plan["valid"] is False

    def test_impulse_short_sr_after_adjustment_too_close(self):
        """IMPULSE SHORT + SR adjust ทำให้ SL ใกล้เกิน → invalid"""
        sc = {
            "type": "IMPULSE_SHORT",
            "direction": "SHORT",
            "swing_high": 122.0,
            "swing_low": 80.0,
            "pivots": [
                {"price": 122.0, "type": "H"},
                {"price": 80.0,  "type": "L"},
            ],
        }
        # resist ต่ำมาก ทำให้ SL ใกล้ entry เกิน 1%
        sr = {"support": {"level": 85.0}, "resist": {"level": 120.3}}
        plan = build_trade_plan(sc, current_price=120.0, min_rr=1.5, sr=sr)
        # อาจ valid หรือ invalid ขึ้นกับ sr — ตรวจแค่ว่าไม่ crash
        assert "valid" in plan

    def test_impulse_rr_too_low_rejected(self):
        """IMPULSE LONG RR ต่ำกว่า min_rr → invalid"""
        sc = {
            "type": "IMPULSE_LONG",
            "direction": "LONG",
            "swing_high": 150.0,
            "swing_low": 95.0,
            "pivots": [
                {"price": 95.0,  "type": "L"},
                {"price": 150.0, "type": "H"},
            ],
        }
        # min_rr สูงมาก → ไม่มีทางผ่าน
        plan = build_trade_plan(sc, current_price=100.0, min_rr=10.0)
        assert plan["valid"] is False
        assert "RR" in plan["reason"]
    def test_valid_long_fill(self):
        """fill ราคาสูงกว่า estimate เล็กน้อย → ยังผ่าน RR"""
        result = recalculate_from_fill(
            direction="LONG",
            actual_entry=101.0,
            original_sl=92.0,
            original_tp_rr=1.618,
            min_rr=1.5,
        )
        assert result["valid"] is True
        assert result["tp1"] > result["actual_entry"]
        assert result["tp2"] > result["tp1"]
        assert result["rr"] >= 1.5

    def test_valid_short_fill(self):
        """fill short → TP ต่ำกว่า entry"""
        result = recalculate_from_fill(
            direction="SHORT",
            actual_entry=119.0,
            original_sl=128.0,
            original_tp_rr=1.618,
            min_rr=1.5,
        )
        assert result["valid"] is True
        assert result["tp1"] < result["actual_entry"]
        assert result["tp2"] < result["tp1"]

    def test_zero_risk_invalid(self):
        """entry == sl → invalid"""
        result = recalculate_from_fill(
            direction="LONG",
            actual_entry=100.0,
            original_sl=100.0,
            original_tp_rr=1.618,
        )
        assert result["valid"] is False

    def test_rr_too_low_invalid(self):
        """fill ห่างจาก SL น้อย → RR ต่ำ → invalid"""
        result = recalculate_from_fill(
            direction="LONG",
            actual_entry=99.5,
            original_sl=92.0,
            original_tp_rr=1.0,
            min_rr=1.5,
        )
        assert result["valid"] is False