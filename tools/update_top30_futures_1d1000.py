# save as: tools/update_top30_futures_1d1000.py
import time
import requests

EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
TICKER_24HR    = "https://fapi.binance.com/fapi/v1/ticker/24hr"

DAYS_REQUIRED = 1000
MS_PER_DAY = 24 * 60 * 60 * 1000

def main():
    now_ms = int(time.time() * 1000)

    ex = requests.get(EXCHANGE_INFO, timeout=20).json()
    symbols = ex.get("symbols", []) or []

    # eligible USDT-M perpetual symbols with onboardDate
    eligible = {}
    for s in symbols:
        if s.get("contractType") != "PERPETUAL":
            continue
        if s.get("quoteAsset") != "USDT":
            continue
        if s.get("status") != "TRADING":
            continue

        onboard = s.get("onboardDate")
        if onboard is None:
            continue

        age_days = (now_ms - int(onboard)) / MS_PER_DAY
        if age_days >= DAYS_REQUIRED:
            eligible[s["symbol"]] = age_days

    tickers = requests.get(TICKER_24HR, timeout=20).json()
    # map symbol -> quoteVolume (USDT)
    vol = {}
    for t in tickers:
        sym = t.get("symbol")
        if sym in eligible:
            try:
                vol[sym] = float(t.get("quoteVolume") or 0.0)
            except Exception:
                vol[sym] = 0.0

    top = sorted(vol.items(), key=lambda x: x[1], reverse=True)[:40]

    print(f"Top 40 (USDT-M PERP) with 1D>={DAYS_REQUIRED} bars (age>= {DAYS_REQUIRED} days)")
    for i, (sym, qv) in enumerate(top, 1):
        print(f"{i:02d}. {sym:<12}  24h_quoteVol={qv:,.0f} USDT   age_days={eligible[sym]:.0f}")

if __name__ == "__main__":
    main()