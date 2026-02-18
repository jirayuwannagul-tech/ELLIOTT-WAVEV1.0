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
    "TRXUSDT",
    "TONUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "ATOMUSDT",
    "UNIUSDT",
    "NEARUSDT",
    "APTUSDT",
    "ICPUSDT",
    "FILUSDT",
    "ARBUSDT",
]

FRACTAL_LEFT = 2
FRACTAL_RIGHT = 2

MAX_SCENARIOS = 3
MIN_RR = 2.0

MAX_RETRY = 3