# app/trading/binance_trader.py
# ติดต่อ Binance Futures API

import os
import time
import hashlib
import hmac
import requests
from typing import Any
from pathlib import Path
from dotenv import load_dotenv

from decimal import Decimal, ROUND_DOWN

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

FUTURES_URL = "https://fapi.binance.com"

BINANCE_POSITION_MODE = (os.getenv("BINANCE_POSITION_MODE") or "ONEWAY").strip().upper()
IS_HEDGE_MODE = BINANCE_POSITION_MODE == "HEDGE"

_EXCHANGE_INFO_CACHE: dict[str, Any] | None = None
_EXCHANGE_INFO_TS: float = 0.0
_EXCHANGE_INFO_TTL_SEC: int = 60


def _get_exchange_info() -> dict[str, Any]:
    global _EXCHANGE_INFO_CACHE, _EXCHANGE_INFO_TS
    now = time.time()
    if _EXCHANGE_INFO_CACHE is not None and (now - _EXCHANGE_INFO_TS) < _EXCHANGE_INFO_TTL_SEC:
        return _EXCHANGE_INFO_CACHE
    r = requests.get(f"{FUTURES_URL}/fapi/v1/exchangeInfo", timeout=10)
    r.raise_for_status()
    data = r.json()
    _EXCHANGE_INFO_CACHE = data
    _EXCHANGE_INFO_TS = now
    return data


def _get_lot_step(symbol: str) -> tuple[float, float]:
    info = _get_exchange_info()
    for s in info.get("symbols", []):
        if s.get("symbol") == symbol:
            for f in s.get("filters", []):
                if f.get("filterType") == "LOT_SIZE":
                    return float(f.get("stepSize", 0)), float(f.get("minQty", 0))
    return 0.0, 0.0

def adjust_quantity(symbol: str, quantity: float) -> float:
    step, min_qty = _get_lot_step(symbol)
    if step <= 0:
        return float(quantity)

    q = Decimal(str(quantity))
    step_d = Decimal(str(step))
    steps = (q / step_d).to_integral_value(rounding=ROUND_DOWN)
    adj = steps * step_d

    if min_qty > 0 and adj < Decimal(str(min_qty)):
        return 0.0

    return float(adj)

def adjust_price(symbol: str, price: float) -> float:
    info = _get_exchange_info()
    for s in info.get("symbols", []):
        if s.get("symbol") == symbol:
            for f in s.get("filters", []):
                if f.get("filterType") == "PRICE_FILTER":
                    tick = float(f.get("tickSize", 0))
                    if tick > 0:
                        p = Decimal(str(price))
                        t = Decimal(str(tick))
                        steps = (p / t).to_integral_value(rounding=ROUND_DOWN)
                        return float(steps * t)
    return float(price)


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
        if asset.get("asset") == "USDT":
            balance = float(asset["balance"])
            print(f"✅ Binance เชื่อมต่อสำเร็จ | ยอด USDT = {balance}", flush=True)
            return balance
    return 0.0


def open_market_order(symbol: str, side: str, quantity: float) -> dict:
    api_key, secret = _get_keys()
    quantity = adjust_quantity(symbol, quantity)
    if quantity <= 0:
        raise ValueError(f"quantity too small after step adjust: {symbol}")
    params: dict[str, Any] = {
        "symbol":    symbol,
        "side":      side,
        "type":      "MARKET",
        "quantity":  quantity,
        "timestamp": int(time.time() * 1000),
    }
    if IS_HEDGE_MODE:
        params["positionSide"] = "LONG" if side == "BUY" else "SHORT"
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/order", params=params, headers=headers, timeout=10)
    print(f"Binance response: {r.text}", flush=True)
    r.raise_for_status()
    return r.json()

def set_stop_loss(symbol: str, side: str, quantity: float, sl_price: float) -> dict:
    api_key, secret = _get_keys()

    open_side = (side or "").upper()
    if open_side not in ("BUY", "SELL"):
        raise ValueError(f"invalid side(open_side): {side}")

    close_side = "SELL" if open_side == "BUY" else "BUY"
    position_side = "LONG" if open_side == "BUY" else "SHORT"

    # 🔥 ปรับ precision ก่อน
    sl_price = adjust_price(symbol, sl_price)

    params: dict[str, Any] = {
        "algoType":      "CONDITIONAL",
        "symbol":        symbol,
        "side":          close_side,
        "type":          "STOP_MARKET",
        "triggerPrice":  sl_price,
        "closePosition": "true",
        "workingType":   "CONTRACT_PRICE",
        "timestamp":     int(time.time() * 1000),
    }

    if IS_HEDGE_MODE:
        params["positionSide"] = position_side

    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/algoOrder", params=params, headers=headers, timeout=10)
    print(f"SL response: {r.text}", flush=True)
    r.raise_for_status()
    return r.json()

def set_take_profit(symbol: str, side: str, quantity: float, tp_price: float) -> dict:
    api_key, secret = _get_keys()

    open_side = (side or "").upper()
    if open_side not in ("BUY", "SELL"):
        raise ValueError(f"invalid side(open_side): {side}")

    close_side = "SELL" if open_side == "BUY" else "BUY"
    position_side = "LONG" if open_side == "BUY" else "SHORT"

    # 🔥 ปรับ precision ก่อน
    tp_price = adjust_price(symbol, tp_price)

    params: dict[str, Any] = {
        "algoType":      "CONDITIONAL",
        "symbol":        symbol,
        "side":          close_side,
        "type":          "TAKE_PROFIT_MARKET",
        "triggerPrice":  tp_price,
        "closePosition": "true",
        "workingType":   "CONTRACT_PRICE",
        "timestamp":     int(time.time() * 1000),
    }

    if IS_HEDGE_MODE:
        params["positionSide"] = position_side

    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/algoOrder", params=params, headers=headers, timeout=10)
    print(f"TP response: {r.text}", flush=True)
    r.raise_for_status()
    return r.json()

def set_leverage(symbol: str, leverage: int = 10) -> None:
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
    api_key, secret = _get_keys()
    params: dict[str, Any] = {
        "symbol":     symbol,
        "marginType": margin_type,
        "timestamp":  int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/marginType", params=params, headers=headers, timeout=10)
    if r.status_code == 400 and "No need to change" in r.text:
        return
    r.raise_for_status()


def get_open_positions() -> list:
    api_key, secret = _get_keys()
    params: dict[str, Any] = {"timestamp": int(time.time() * 1000)}
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.get(f"{FUTURES_URL}/fapi/v2/positionRisk", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    positions = r.json()
    return [p for p in positions if float(p.get("positionAmt", 0)) != 0]


def cancel_order(symbol: str, order_id: int) -> dict:
    api_key, secret = _get_keys()
    params: dict[str, Any] = {
        "symbol":    symbol,
        "orderId":   order_id,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.delete(f"{FUTURES_URL}/fapi/v1/order", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

# เพิ่มท้ายไฟล์ app/trading/binance_trader.py

def get_mark_price(symbol: str) -> float:
    r = requests.get(f"{FUTURES_URL}/fapi/v1/premiumIndex", params={"symbol": symbol}, timeout=10)
    r.raise_for_status()
    j = r.json()
    return float(j.get("markPrice") or 0)

def close_market_reduce_only(symbol: str, side: str, quantity: float, position_side: str | None = None) -> dict:
    """
    ปิดบางส่วน/ทั้งหมดด้วย MARKET + reduceOnly
    side = "BUY"/"SELL" (ฝั่งปิด)
    position_side = "LONG"/"SHORT" (ใช้เฉพาะ hedge mode)
    """
    api_key, secret = _get_keys()
    quantity = adjust_quantity(symbol, quantity)
    if quantity <= 0:
        raise ValueError(f"quantity too small after step adjust: {symbol}")

    params: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
        "reduceOnly": "true",
        "timestamp": int(time.time() * 1000),
    }
    if IS_HEDGE_MODE:
        if position_side not in ("LONG", "SHORT"):
            raise ValueError(f"invalid position_side: {position_side}")
        params["positionSide"] = position_side

    params["signature"] = _sign(params, secret)
    headers = {"X-MBX-APIKEY": api_key}
    r = requests.post(f"{FUTURES_URL}/fapi/v1/order", params=params, headers=headers, timeout=10)
    print(f"REDUCE response: {r.text}", flush=True)
    r.raise_for_status()
    return r.json()