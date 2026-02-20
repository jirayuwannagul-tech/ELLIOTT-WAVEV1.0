# app/trading/binance_trader.py
# ติดต่อ Binance Futures API
# ยังไม่เปิดใช้งาน - ทดสอบบน testnet ก่อน

import os
import time
import hashlib
import hmac
import requests
from typing import Any
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

FUTURES_URL = "https://fapi.binance.com"          # mainnet
# FUTURES_URL = "https://testnet.binancefuture.com"  # testnet
#FUTURES_URL = "https://demo-fapi.binance.com"        # demo

def _get_keys() -> tuple[str, str]:
    api_key = os.getenv("BINANCE_API_KEY", "")
    secret = os.getenv("BINANCE_SECRET_KEY", "")
    return api_key, secret

def _sign(params: dict[str, Any], secret: str) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()

def get_balance() -> float:
    api_key, secret = _get_keys()
    params: dict[str, Any] = {"timestamp": int(time.time() * 1000)}
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.get(f"{FUTURES_URL}/fapi/v2/balance", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    for asset in r.json():
        if asset["asset"] == "USDT":
            return float(asset["balance"])
    return 0.0

def open_market_order(symbol: str, side: str, quantity: float) -> dict:
    api_key, secret = _get_keys()
    params: dict[str, Any] = {
        "symbol":    symbol,
        "side":      side,
        "type":      "MARKET",
        "quantity":  quantity,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/order", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def set_stop_loss(symbol: str, side: str, quantity: float, sl_price: float) -> dict:
    api_key, secret = _get_keys()
    close_side = "SELL" if side == "BUY" else "BUY"
    params: dict[str, Any] = {
        "symbol":     symbol,
        "side":       close_side,
        "type":       "STOP_MARKET",
        "stopPrice":  sl_price,
        "quantity":   quantity,
        "reduceOnly": "true",
        "timestamp":  int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/order", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def set_take_profit(symbol: str, side: str, quantity: float, tp_price: float) -> dict:
    api_key, secret = _get_keys()
    close_side = "SELL" if side == "BUY" else "BUY"
    params: dict[str, Any] = {
        "symbol":     symbol,
        "side":       close_side,
        "type":       "TAKE_PROFIT_MARKET",
        "stopPrice":  tp_price,
        "quantity":   quantity,
        "reduceOnly": "true",
        "timestamp":  int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/order", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def set_leverage(symbol: str, leverage: int = 10) -> None:
    """ ตั้ง leverage x10 """
    api_key, secret = _get_keys()
    params: dict[str, Any] = {
        "symbol":    symbol,
        "leverage":  leverage,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/leverage", params=params, headers=headers, timeout=10)
    r.raise_for_status()


def set_margin_type(symbol: str, margin_type: str = "ISOLATED") -> None:
    """ ตั้ง ISOLATED หรือ CROSSED """
    api_key, secret = _get_keys()
    params: dict[str, Any] = {
        "symbol":     symbol,
        "marginType": margin_type,
        "timestamp":  int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/marginType", params=params, headers=headers, timeout=10)
    r.raise_for_status()
