from app.trading.binance_trader import get_balance
try:
    balance = get_balance()
    print(f'✅ ยอด USDT = {balance}')
except Exception as e:
    print(f'❌ {e}')
