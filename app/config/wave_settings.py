from zoneinfo import ZoneInfo

TIMEFRAME = "1d"
BARS = 1000

TIMEZONE = ZoneInfo("Asia/Bangkok")
RUN_HOUR = 7
RUN_MINUTE = 5

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT",
]
MAX_RETRY = 3
# --- Position sizing (fixed notional per trade) ---
DEFAULT_NOTIONAL_USDT = 3.5

# Override per symbol when DEFAULT is too small to pass Binance minQty/step.
# NOTE: BTC needs a much larger notional because minQty is 0.001 BTC.
NOTIONAL_MAP = {
    "BTCUSDT": 70.0,
    "BNBUSDT": 6.5,
    "AVAXUSDT": 10.0,
     "SOLUSDT": 8.0,
}

FRACTAL_LEFT = 2
FRACTAL_RIGHT = 2

MAX_SCENARIOS = 3
MIN_RR = 1.5
MIN_CONFIDENCE_LIVE = 65.0
MIN_CONFIDENCE_BACKTEST = 65.0
ABC_CONFIRM_BUFFER = 0.01
