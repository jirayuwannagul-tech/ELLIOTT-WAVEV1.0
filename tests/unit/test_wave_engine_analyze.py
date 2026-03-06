import pandas as pd

from app.analysis import wave_engine


def _make_df(rows: int = 260, close: float = 100.0) -> pd.DataFrame:
    data = {
        "open": [close] * rows,
        "high": [close + 1] * rows,
        "low": [close - 1] * rows,
        "close": [close] * rows,
        "volume": [1000] * rows,
        "ema50": [110.0] * rows,
        "ema200": [100.0] * rows,
        "rsi14": [55.0] * rows,
        "atr14": [1.0] * rows,
        "volume_ma20": [900.0] * rows,
    }

    df = pd.DataFrame(data)

    # ทำให้ ema200 slope ขึ้น
    df.loc[rows - 2, "ema200"] = 99.0

    return df

def test_send_log_no_vps_url(monkeypatch):
    called = {"post": 0}

    def fake_post(*args, **kwargs):
        called["post"] += 1
        return None

    monkeypatch.setattr(wave_engine.req, "post", fake_post)
    monkeypatch.setenv("VPS_URL", "")
    monkeypatch.setenv("EXEC_TOKEN", "")

    wave_engine._send_log("hello")

    assert called["post"] == 0


def test_send_log_with_vps_url(monkeypatch):
    called = {"post": 0, "url": None, "json": None, "headers": None}

    def fake_post(url, json=None, headers=None, timeout=None):
        called["post"] += 1
        called["url"] = url
        called["json"] = json
        called["headers"] = headers
        return None

    monkeypatch.setattr(wave_engine.req, "post", fake_post)
    monkeypatch.setenv("VPS_URL", "http://localhost:8000")
    monkeypatch.setenv("EXEC_TOKEN", "abc123")

    wave_engine._send_log("hello world")

    assert called["post"] == 1
    assert called["url"] == "http://localhost:8000/log"
    assert called["json"] == {"msg": "hello world"}
    assert called["headers"] == {"X-EXEC-TOKEN": "abc123"}


def test_analyze_symbol_returns_none_when_not_enough_bars(monkeypatch):
    df = _make_df(rows=200)

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)

    result = wave_engine.analyze_symbol("BTCUSDT")

    assert result is None


def test_analyze_symbol_sideway_path(monkeypatch):
    df = _make_df()

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)
    monkeypatch.setattr(wave_engine, "add_ema", lambda x, lengths=None: x)
    monkeypatch.setattr(wave_engine, "add_rsi", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_atr", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_volume_ma", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "trend_filter_ema", lambda x: "BULL")
    monkeypatch.setattr(wave_engine, "volume_spike", lambda *a, **k: False)
    monkeypatch.setattr(wave_engine, "detect_market_mode", lambda x: "SIDEWAY")
    monkeypatch.setattr(
        wave_engine,
        "get_mtf_summary",
        lambda symbol: {
            "weekly_permit_long": True,
            "weekly_permit_short": True,
            "h4_confirm_long": True,
            "h4_confirm_short": True,
        },
    )

    result = wave_engine.analyze_symbol("BTCUSDT")
    assert result is not None

    assert isinstance(result, dict)
    assert "sideway" in result
    assert "scenarios" in result


def test_analyze_symbol_not_enough_pivots(monkeypatch):
    df = _make_df()

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)
    monkeypatch.setattr(wave_engine, "add_ema", lambda x, lengths=None: x)
    monkeypatch.setattr(wave_engine, "add_rsi", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_atr", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_volume_ma", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "trend_filter_ema", lambda x: "BULL")
    monkeypatch.setattr(wave_engine, "volume_spike", lambda *a, **k: False)
    monkeypatch.setattr(wave_engine, "detect_market_mode", lambda x: "TREND")
    monkeypatch.setattr(wave_engine, "get_mtf_summary", lambda symbol: {})
    monkeypatch.setattr(
        wave_engine,
        "find_fractal_pivots",
        lambda x: [{"type": "L", "price": 100}] * 3,
    )
    monkeypatch.setattr(
        wave_engine,
        "filter_pivots",
        lambda pivots, min_pct_move=None: pivots,
    )
    monkeypatch.setattr(wave_engine, "label_pivot_chain", lambda pivots: "NOISE")
    monkeypatch.setattr(wave_engine, "build_zones_from_pivots", lambda df: [])
    monkeypatch.setattr(
        wave_engine,
        "nearest_support_resist",
        lambda zones, price=None: {},
    )

    result = wave_engine.analyze_symbol("BTCUSDT")
    assert result is not None

    assert result["scenarios"] == []
    assert result["message"] == "โครงสร้างยังไม่ชัด"


def test_analyze_symbol_fallback_scenario_blocked(monkeypatch):
    df = _make_df()
    pivots = [
        {"type": "L", "price": 100, "index": 1, "degree": "intermediate"},
        {"type": "H", "price": 120, "index": 2, "degree": "intermediate"},
        {"type": "L", "price": 110, "index": 3, "degree": "intermediate"},
        {"type": "H", "price": 130, "index": 4, "degree": "intermediate"},
    ]

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)
    monkeypatch.setattr(wave_engine, "add_ema", lambda x, lengths=None: x)
    monkeypatch.setattr(wave_engine, "add_rsi", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_atr", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_volume_ma", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "trend_filter_ema", lambda x: "BULL")
    monkeypatch.setattr(wave_engine, "volume_spike", lambda *a, **k: False)
    monkeypatch.setattr(wave_engine, "detect_market_mode", lambda x: "TREND")
    monkeypatch.setattr(
        wave_engine,
        "get_mtf_summary",
        lambda symbol: {
            "weekly_permit_long": True,
            "weekly_permit_short": True,
            "h4_confirm_long": True,
            "h4_confirm_short": True,
        },
    )
    monkeypatch.setattr(wave_engine, "find_fractal_pivots", lambda x: pivots)
    monkeypatch.setattr(
        wave_engine,
        "filter_pivots",
        lambda pivots, min_pct_move=None: pivots,
    )
    monkeypatch.setattr(wave_engine, "label_pivot_chain", lambda pivots: "IMPULSE")
    monkeypatch.setattr(wave_engine, "build_zones_from_pivots", lambda df: [])
    monkeypatch.setattr(
        wave_engine,
        "nearest_support_resist",
        lambda zones, price=None: {},
    )
    monkeypatch.setattr(
        wave_engine,
        "build_scenarios",
        lambda *a, **k: [
            {
                "type": "IMPULSE_LONG",
                "phase": "fallback",
                "direction": "LONG",
                "probability": 80,
                "confidence": 80,
                "pivots": pivots,
                "reasons": ["fallback"],
                "is_fallback": True,
            }
        ],
    )
    monkeypatch.setattr(
        wave_engine,
        "detect_market_regime",
        lambda df: {"regime": "TREND", "trend": "BULL", "vol": "MID"},
    )
    monkeypatch.setattr(
        wave_engine,
        "compute_macro_bias",
        lambda regime, rsi14=50.0: {
            "bias": "LONG",
            "strength": 70,
            "allow_long": True,
            "allow_short": False,
        },
    )
    monkeypatch.setattr(
        wave_engine,
        "apply_context_gate",
        lambda scenario, macro_bias, min_confidence: scenario,
    )
    monkeypatch.setattr(
        wave_engine,
        "build_trade_plan",
        lambda scenario, current_price, min_rr, sr=None: {
            "valid": True,
            "entry": 99.0,
            "sl": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
        },
    )

    result = wave_engine.analyze_symbol("BTCUSDT")
    assert result is not None

    assert len(result["scenarios"]) == 1
    assert result["scenarios"][0]["context_allowed"] is False
    assert result["scenarios"][0]["status"] == "BLOCKED"


def test_analyze_symbol_trend_block(monkeypatch):
    df = _make_df(close=100.0)
    df.loc[:, "ema50"] = 90.0
    df.loc[:, "ema200"] = 100.0

    pivots = [
        {"type": "L", "price": 100, "index": 1, "degree": "intermediate"},
        {"type": "H", "price": 120, "index": 2, "degree": "intermediate"},
        {"type": "L", "price": 110, "index": 3, "degree": "intermediate"},
        {"type": "H", "price": 130, "index": 4, "degree": "intermediate"},
    ]

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)
    monkeypatch.setattr(wave_engine, "add_ema", lambda x, lengths=None: x)
    monkeypatch.setattr(wave_engine, "add_rsi", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_atr", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_volume_ma", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "trend_filter_ema", lambda x: "BULL")
    monkeypatch.setattr(wave_engine, "volume_spike", lambda *a, **k: False)
    monkeypatch.setattr(wave_engine, "detect_market_mode", lambda x: "TREND")
    monkeypatch.setattr(
        wave_engine,
        "get_mtf_summary",
        lambda symbol: {
            "weekly_permit_long": True,
            "weekly_permit_short": True,
            "h4_confirm_long": True,
            "h4_confirm_short": True,
        },
    )
    monkeypatch.setattr(wave_engine, "find_fractal_pivots", lambda x: pivots)
    monkeypatch.setattr(
        wave_engine,
        "filter_pivots",
        lambda pivots, min_pct_move=None: pivots,
    )
    monkeypatch.setattr(wave_engine, "label_pivot_chain", lambda pivots: "IMPULSE")
    monkeypatch.setattr(wave_engine, "build_zones_from_pivots", lambda df: [])
    monkeypatch.setattr(
        wave_engine,
        "nearest_support_resist",
        lambda zones, price=None: {},
    )
    monkeypatch.setattr(
        wave_engine,
        "build_scenarios",
        lambda *a, **k: [
            {
                "type": "IMPULSE_LONG",
                "phase": "trend",
                "direction": "LONG",
                "probability": 80,
                "confidence": 80,
                "pivots": pivots,
                "reasons": ["trend"],
                "is_fallback": False,
            }
        ],
    )
    monkeypatch.setattr(
        wave_engine,
        "detect_market_regime",
        lambda df: {"regime": "TREND", "trend": "BULL", "vol": "MID"},
    )
    monkeypatch.setattr(
        wave_engine,
        "compute_macro_bias",
        lambda regime, rsi14=50.0: {
            "bias": "LONG",
            "strength": 70,
            "allow_long": True,
            "allow_short": False,
        },
    )
    monkeypatch.setattr(
        wave_engine,
        "apply_context_gate",
        lambda scenario, macro_bias, min_confidence: dict(
            scenario,
            context_score=80,
        ),
    )
    monkeypatch.setattr(
        wave_engine,
        "build_trade_plan",
        lambda scenario, current_price, min_rr, sr=None: {
            "valid": True,
            "entry": 99.0,
            "sl": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
        },
    )

    result = wave_engine.analyze_symbol("BTCUSDT")
    assert result is not None

    assert result["scenarios"] == []


def test_analyze_symbol_abc_up_triggered(monkeypatch):
    df = _make_df(close=100.0)
    pivots = [
        {"type": "L", "price": 100, "index": 1, "degree": "intermediate"},
        {"type": "H", "price": 120, "index": 2, "degree": "intermediate"},
        {"type": "L", "price": 110, "index": 3, "degree": "intermediate"},
        {"type": "H", "price": 130, "index": 4, "degree": "intermediate"},
    ]

    called = {"post": 0}

    def fake_post(*args, **kwargs):
        called["post"] += 1
        return None

    monkeypatch.setattr(wave_engine.req, "post", fake_post)
    monkeypatch.setenv("VPS_URL", "http://localhost:8000")
    monkeypatch.setenv("EXEC_TOKEN", "abc123")

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)
    monkeypatch.setattr(wave_engine, "add_ema", lambda x, lengths=None: x)
    monkeypatch.setattr(wave_engine, "add_rsi", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_atr", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_volume_ma", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "trend_filter_ema", lambda x: "BULL")
    monkeypatch.setattr(wave_engine, "volume_spike", lambda *a, **k: True)
    monkeypatch.setattr(wave_engine, "detect_market_mode", lambda x: "TREND")
    monkeypatch.setattr(
        wave_engine,
        "get_mtf_summary",
        lambda symbol: {
            "weekly_permit_long": True,
            "weekly_permit_short": True,
            "h4_confirm_long": True,
            "h4_confirm_short": True,
        },
    )
    monkeypatch.setattr(wave_engine, "find_fractal_pivots", lambda x: pivots)
    monkeypatch.setattr(
        wave_engine,
        "filter_pivots",
        lambda pivots, min_pct_move=None: pivots,
    )
    monkeypatch.setattr(wave_engine, "label_pivot_chain", lambda pivots: "ABC")
    monkeypatch.setattr(wave_engine, "build_zones_from_pivots", lambda df: [])
    monkeypatch.setattr(
        wave_engine,
        "nearest_support_resist",
        lambda zones, price=None: {},
    )
    monkeypatch.setattr(
        wave_engine,
        "build_scenarios",
        lambda *a, **k: [
            {
                "type": "ABC_UP",
                "phase": "abc",
                "direction": "LONG",
                "probability": 80,
                "confidence": 80,
                "pivots": pivots,
                "reasons": ["abc"],
                "is_fallback": False,
            }
        ],
    )
    monkeypatch.setattr(
        wave_engine,
        "detect_market_regime",
        lambda df: {"regime": "TREND", "trend": "BULL", "vol": "MID"},
    )
    monkeypatch.setattr(
        wave_engine,
        "compute_macro_bias",
        lambda regime, rsi14=50.0: {
            "bias": "LONG",
            "strength": 70,
            "allow_long": True,
            "allow_short": False,
        },
    )
    monkeypatch.setattr(
        wave_engine,
        "apply_context_gate",
        lambda scenario, macro_bias, min_confidence: dict(
            scenario,
            context_score=80,
        ),
    )
    monkeypatch.setattr(
        wave_engine,
        "build_trade_plan",
        lambda scenario, current_price, min_rr, sr=None: {
            "valid": True,
            "entry": 99.0,
            "sl": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
        },
    )

    result = wave_engine.analyze_symbol("BTCUSDT")
    assert result is not None

    assert len(result["scenarios"]) == 1
    assert result["scenarios"][0]["trade_plan"]["triggered"] is True
    assert called["post"] >= 2


def test_analyze_symbol_execute_skipped_when_bad_vps_url(monkeypatch):
    df = _make_df(close=100.0)
    pivots = [
        {"type": "L", "price": 100, "index": 1, "degree": "intermediate"},
        {"type": "H", "price": 120, "index": 2, "degree": "intermediate"},
        {"type": "L", "price": 110, "index": 3, "degree": "intermediate"},
        {"type": "H", "price": 130, "index": 4, "degree": "intermediate"},
    ]

    called = {"post": 0}

    def fake_post(*args, **kwargs):
        called["post"] += 1
        return None

    monkeypatch.setattr(wave_engine.req, "post", fake_post)
    monkeypatch.setenv("VPS_URL", "localhost:8000")
    monkeypatch.setenv("EXEC_TOKEN", "abc123")

    monkeypatch.setattr(wave_engine, "fetch_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(wave_engine, "drop_unclosed_candle", lambda x: x)
    monkeypatch.setattr(wave_engine, "add_ema", lambda x, lengths=None: x)
    monkeypatch.setattr(wave_engine, "add_rsi", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_atr", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "add_volume_ma", lambda x, length=None: x)
    monkeypatch.setattr(wave_engine, "trend_filter_ema", lambda x: "BULL")
    monkeypatch.setattr(wave_engine, "volume_spike", lambda *a, **k: True)
    monkeypatch.setattr(wave_engine, "detect_market_mode", lambda x: "TREND")
    monkeypatch.setattr(
        wave_engine,
        "get_mtf_summary",
        lambda symbol: {
            "weekly_permit_long": True,
            "weekly_permit_short": True,
            "h4_confirm_long": True,
            "h4_confirm_short": True,
        },
    )
    monkeypatch.setattr(wave_engine, "find_fractal_pivots", lambda x: pivots)
    monkeypatch.setattr(
        wave_engine,
        "filter_pivots",
        lambda pivots, min_pct_move=None: pivots,
    )
    monkeypatch.setattr(wave_engine, "label_pivot_chain", lambda pivots: "IMPULSE")
    monkeypatch.setattr(wave_engine, "build_zones_from_pivots", lambda df: [])
    monkeypatch.setattr(
        wave_engine,
        "nearest_support_resist",
        lambda zones, price=None: {},
    )
    monkeypatch.setattr(
        wave_engine,
        "build_scenarios",
        lambda *a, **k: [
            {
                "type": "IMPULSE_LONG",
                "phase": "trend",
                "direction": "LONG",
                "probability": 80,
                "confidence": 80,
                "pivots": pivots,
                "reasons": ["trend"],
                "is_fallback": False,
            }
        ],
    )
    monkeypatch.setattr(
        wave_engine,
        "detect_market_regime",
        lambda df: {"regime": "TREND", "trend": "BULL", "vol": "MID"},
    )
    monkeypatch.setattr(
        wave_engine,
        "compute_macro_bias",
        lambda regime, rsi14=50.0: {
            "bias": "LONG",
            "strength": 70,
            "allow_long": True,
            "allow_short": False,
        },
    )
    monkeypatch.setattr(
        wave_engine,
        "apply_context_gate",
        lambda scenario, macro_bias, min_confidence: dict(
            scenario,
            context_score=80,
        ),
    )
    monkeypatch.setattr(
        wave_engine,
        "build_trade_plan",
        lambda scenario, current_price, min_rr, sr=None: {
            "valid": True,
            "entry": 99.0,
            "sl": 95.0,
            "tp1": 105.0,
            "tp2": 110.0,
        },
    )

    result = wave_engine.analyze_symbol("BTCUSDT")
    assert result is not None

    assert len(result["scenarios"]) == 1
    assert result["scenarios"][0]["trade_plan"]["triggered"] is True
    assert called["post"] >= 1