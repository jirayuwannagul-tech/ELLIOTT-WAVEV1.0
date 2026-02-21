import sys
import os
import subprocess
import threading
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request
import requests
from app.scheduler.daily_wave_scheduler import run_daily_wave_job, run_trend_watch_job
from app.trading.trade_executor import execute_signal
from app.trading.binance_trader import get_balance, get_open_positions

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Elliott Bot Dashboard</title>
<meta http-equiv="refresh" content="30">
<style>
  body { font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }
  h1 { color: #00d4ff; }
  .card { background: #16213e; border-radius: 8px; padding: 15px; margin: 10px 0; }
  .green { color: #00ff88; }
  .red { color: #ff4444; }
  button { background: #00d4ff; color: #000; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; font-size: 14px; }
  pre { background: #0a0a1a; padding: 10px; border-radius: 5px; font-size: 12px; max-height: 300px; overflow-y: auto; }
</style>
</head>
<body>
<h1>🌊 Elliott Bot Dashboard</h1>

<div class="card">
  <h2>💰 ยอด USDT</h2>
  <h2 class="green">BALANCE_PLACEHOLDER USDT</h2>
</div>

<div class="card">
  <h2>📊 Position ที่เปิดอยู่</h2>
  POSITION_PLACEHOLDER
</div>

<div class="card">
  <h2>⚙️ Actions</h2>
  <form method="POST" action="/dashboard/run">
    <input type="hidden" name="token" value="TOKEN_PLACEHOLDER">
    <button type="submit">▶️ Manual Run</button>
  </form>
</div>

<div class="card">
  <h2>📋 Log ล่าสุด</h2>
  <pre>LOG_PLACEHOLDER</pre>
</div>

</body>
</html>
"""

@app.route("/dashboard", methods=["GET"])
def dashboard():
    token = request.args.get("token", "")
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    if token != expected:
        return "FORBIDDEN - ใส่ ?token=YOUR_TOKEN", 403

    try:
        balance = f"{get_balance():.2f}"
    except Exception:
        balance = "เชื่อมต่อไม่ได้"

    try:
        positions = get_open_positions()
        pos_html = ""
        for p in positions:
            sym = p["symbol"]
            amt = p["positionAmt"]
            pnl = float(p["unRealizedProfit"])
            color = "green" if pnl >= 0 else "red"
            pos_html += f'<p>{sym} | จำนวน: {amt} | PNL: <span class="{color}">{pnl:.2f} USDT</span></p>'
        if not pos_html:
            pos_html = "<p>ไม่มี position เปิดอยู่</p>"
    except Exception:
        pos_html = "<p>ดึงข้อมูลไม่ได้</p>"

    try:
        log = subprocess.check_output(
            ["tail", "-50", "/root/ELLIOTT-WAVEV1.0/server.log"],
            text=True
        )
    except Exception:
        log = "ไม่พบ log"

    html = DASHBOARD_HTML
    html = html.replace("BALANCE_PLACEHOLDER", balance)
    html = html.replace("POSITION_PLACEHOLDER", pos_html)
    html = html.replace("LOG_PLACEHOLDER", log)
    html = html.replace("TOKEN_PLACEHOLDER", token)
    return html

@app.route("/dashboard/run", methods=["POST"])
def dashboard_run():
    token = request.form.get("token", "")
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    if token != expected:
        return "FORBIDDEN", 403
    threading.Thread(target=run_daily_wave_job).start()
    return f'<meta http-equiv="refresh" content="3;url=/dashboard?token={token}">Running...'

@app.route("/")
def health():
    return "OK", 200

@app.route("/debug/ip")
def debug_ip():
    try:
        ipv4 = requests.get("https://api.ipify.org", timeout=10).text.strip()
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500
    return {"ok": True, "ipv4": ipv4}, 200

@app.route("/trend-watch", methods=["POST"])
def trend_watch():
    run_trend_watch_job(min_conf=65.0)
    return "OK", 200

@app.route("/run-daily", methods=["POST"])
def run_daily():
    expected = (os.getenv("CRON_TOKEN") or "").strip()
    got = (request.headers.get("X-CRON-TOKEN") or "").strip()
    if expected and got != expected:
        return "FORBIDDEN", 403
    run_daily_wave_job()
    return "OK", 200

@app.route("/execute", methods=["POST"])
def execute():
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    got = (request.headers.get("X-EXEC-TOKEN") or "").strip()
    if expected and got != expected:
        return "FORBIDDEN", 403
    payload = request.get_json(silent=True) or {}
    ok = execute_signal(payload)
    return {"ok": bool(ok)}, 200

@app.route("/log", methods=["POST"])
def receive_log():
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    got = (request.headers.get("X-EXEC-TOKEN") or "").strip()
    if expected and got != expected:
        return "FORBIDDEN", 403
    payload = request.get_json(silent=True) or {}
    msg = payload.get("msg", "")
    print(f"[RAILWAY] {msg}", flush=True)
    return {"ok": True}, 200

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        print("Manual Run Mode...")
        run_daily_wave_job()
    elif len(sys.argv) > 1 and sys.argv[1] == "trend-watch":
        print("Manual Trend Watch Mode...")
        run_trend_watch_job(min_conf=65.0)
    else:
        app.run(host="0.0.0.0", port=8080)