import pandas as pd

from app.analysis.wave_engine import analyze_symbol
from app.data.binance_fetcher import fetch_ohlcv


def run_backtest(symbol="BTCUSDT", tf="1d", limit=1000):

    df = fetch_ohlcv(symbol, tf, limit=limit)

    trades = []

    for i in range(300, len(df)):

        slice_df = df.iloc[:i]

        result = analyze_symbol(symbol)

        if not result:
            continue

        plan = result.get("trade_plan")

        if not plan:
            continue

        entry = plan["entry"]
        sl = plan["sl"]
        tp = plan["tp"]

        outcome = simulate_trade(df.iloc[i:], entry, sl, tp)

        trades.append({
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "result": outcome
        })

    return trades


def simulate_trade(df, entry, sl, tp):

    for _, row in df.iterrows():

        if row["low"] <= sl:
            return "SL"

        if row["high"] >= tp:
            return "TP"

    return "OPEN"


def summarize(trades):

    wins = sum(1 for t in trades if t["result"] == "TP")
    losses = sum(1 for t in trades if t["result"] == "SL")

    total = len(trades)

    if total == 0:
        return {}

    winrate = wins / total

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "winrate": winrate
    }


if __name__ == "__main__":

    trades = run_backtest("BTCUSDT")

    stats = summarize(trades)

    print(stats)