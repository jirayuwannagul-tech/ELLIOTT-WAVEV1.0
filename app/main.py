import sys
import os
import subprocess
import threading
from dotenv import load_dotenv
load_dotenv()
os.environ["TZ"] = "Asia/Bangkok"
import time
time.tzset()
from flask import Flask, request
import requests
from app.scheduler.daily_wave_scheduler import run_daily_wave_job, run_trend_watch_job
from app.trading.trade_executor import execute_signal
from app.state.position_manager import get_active, _load_position, _key
from app.config.wave_settings import TIMEFRAME      
from app.trading.binance_trader import get_balance, get_open_positions

app = Flask(__name__)
_balance_cache = {"value": None, "ts": 0}

from app.performance.dashboard import perf_bp
app.register_blueprint(perf_bp)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ELLIOTT QUANTUM — CONTROL</title>
<meta http-equiv="refresh" content="30">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root{--bg:#00040a;--cyan:#00f5ff;--green:#00ff9d;--red:#ff1744;--yellow:#ffea00;--panel:rgba(0,20,40,0.85);--border:rgba(0,245,255,0.12);--border-hot:rgba(0,245,255,0.4);--text:#8ab8d0;--dim:#1a4060}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--bg);color:var(--text);font-family:'Share Tech Mono',monospace;font-size:12px;overflow-x:hidden}
.space-bg{position:fixed;inset:0;z-index:0;background:radial-gradient(ellipse 80% 60% at 20% 50%,rgba(0,50,100,0.25),transparent 60%),radial-gradient(ellipse 60% 80% at 80% 30%,rgba(40,0,80,0.2),transparent 60%),#00040a}
.stars{position:fixed;inset:0;z-index:0;background-image:radial-gradient(1px 1px at 10% 15%,rgba(255,255,255,0.6),transparent),radial-gradient(1px 1px at 25% 40%,rgba(255,255,255,0.4),transparent),radial-gradient(1.5px 1.5px at 40% 10%,rgba(255,255,255,0.7),transparent),radial-gradient(1px 1px at 70% 25%,rgba(255,255,255,0.5),transparent),radial-gradient(1px 1px at 85% 5%,rgba(255,255,255,0.6),transparent),radial-gradient(1px 1px at 48% 33%,rgba(0,245,255,0.4),transparent),radial-gradient(1px 1px at 72% 58%,rgba(176,64,255,0.3),transparent)}
.scanlines{position:fixed;inset:0;z-index:1;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,245,255,0.008) 3px,rgba(0,245,255,0.008) 4px);pointer-events:none}
.grid-overlay{position:fixed;inset:0;z-index:1;background-image:linear-gradient(rgba(0,245,255,0.018) 1px,transparent 1px),linear-gradient(90deg,rgba(0,245,255,0.018) 1px,transparent 1px);background-size:60px 60px;pointer-events:none}
.vignette{position:fixed;inset:0;z-index:2;background:radial-gradient(ellipse at center,transparent 50%,rgba(0,2,8,0.7));pointer-events:none}
.root{position:relative;z-index:10;padding:18px 22px 48px;max-width:1100px;margin:0 auto}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding-bottom:16px;position:relative;border-bottom:1px solid var(--border-hot)}
.header::after{content:'';position:absolute;bottom:-1px;left:0;width:320px;height:1px;background:linear-gradient(90deg,var(--cyan),transparent)}
.logo-wrap{display:flex;align-items:center;gap:16px}
.logo-hex{width:48px;height:48px;position:relative;display:flex;align-items:center;justify-content:center;font-size:20px}
.logo-hex::before{content:'';position:absolute;inset:0;border:1px solid var(--border-hot);border-radius:6px;box-shadow:0 0 24px rgba(0,245,255,0.25);animation:hex-pulse 4s ease-in-out infinite}
@keyframes hex-pulse{0%,100%{box-shadow:0 0 24px rgba(0,245,255,0.25)}50%{box-shadow:0 0 40px rgba(0,245,255,0.45)}}
.logo-main{font-family:'Orbitron',monospace;font-size:18px;font-weight:900;letter-spacing:4px;color:var(--cyan);text-shadow:0 0 20px rgba(0,245,255,0.5)}
.logo-sub{font-size:9px;letter-spacing:3px;color:var(--dim);text-transform:uppercase;margin-top:2px}
.header-right{display:flex;align-items:center;gap:12px}
.live-badge{display:flex;align-items:center;gap:8px;padding:6px 14px;border:1px solid rgba(0,255,157,0.3);border-radius:2px;background:rgba(0,255,157,0.05);font-size:10px;letter-spacing:2px;color:var(--green)}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green);animation:blink 1.5s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.2}}
.sys-tag{font-size:9px;letter-spacing:2px;padding:5px 12px;border:1px solid rgba(0,245,255,0.2);border-radius:2px;color:rgba(0,245,255,0.5)}
.panel{position:relative;background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:16px;backdrop-filter:blur(10px);margin-bottom:12px}
.panel::before,.panel::after,.panel .c1,.panel .c2{content:'';position:absolute;width:10px;height:10px;border-color:var(--cyan);border-style:solid;opacity:0.3}
.panel::before{top:0;left:0;border-width:1px 0 0 1px}
.panel::after{top:0;right:0;border-width:1px 1px 0 0}
.panel .c1{bottom:0;left:0;border-width:0 0 1px 1px}
.panel .c2{bottom:0;right:0;border-width:0 1px 1px 0}
.panel-title{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--cyan);display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border);text-shadow:0 0 10px rgba(0,245,255,0.5)}
.panel-title::before{content:'';width:2px;height:12px;background:var(--cyan);box-shadow:0 0 8px var(--cyan);flex-shrink:0}
.balance{font-family:'Orbitron',monospace;font-size:36px;font-weight:700;color:var(--green);text-shadow:0 0 20px rgba(0,255,157,0.4);letter-spacing:-1px}
.balance-unit{font-size:14px;opacity:0.5;margin-left:4px}
.pos-row{padding:10px 0;border-bottom:1px solid rgba(0,245,255,0.05);font-size:11px;line-height:1.8}
.pos-row:last-child{border-bottom:none}
.pos-sym{font-family:'Orbitron',monospace;font-size:11px;color:var(--cyan);font-weight:700}
.pnl-green{color:var(--green)}
.pnl-red{color:var(--red)}
.empty-pos{color:var(--dim);letter-spacing:2px;font-size:10px}
.run-btn{font-family:'Orbitron',monospace;font-size:10px;letter-spacing:2px;padding:10px 24px;background:rgba(0,245,255,0.08);border:1px solid var(--border-hot);border-radius:3px;color:var(--cyan);cursor:pointer;transition:all 0.2s;text-shadow:0 0 10px rgba(0,245,255,0.3)}
.run-btn:hover{background:rgba(0,245,255,0.15);box-shadow:0 0 20px rgba(0,245,255,0.2)}
pre{background:rgba(0,0,0,0.4);border:1px solid var(--border);border-radius:3px;padding:12px;font-size:10px;max-height:300px;overflow-y:auto;line-height:1.6;color:var(--text)}
pre::-webkit-scrollbar{width:3px}
pre::-webkit-scrollbar-thumb{background:var(--dim);border-radius:2px}
.footer{margin-top:16px;font-size:9px;letter-spacing:2px;color:var(--dim);border-top:1px solid var(--border);padding-top:12px;display:flex;justify-content:space-between}
.footer a{color:var(--dim);text-decoration:none}
.footer a:hover{color:var(--cyan)}
</style>
</head>
<body>
<div class="space-bg"></div>
<div class="stars"></div>
<div class="scanlines"></div>
<div class="grid-overlay"></div>
<div class="vignette"></div>
<div class="root">
  <div class="header">
    <div class="logo-wrap">
      <div class="logo-hex">🌊</div>
      <div>
        <div class="logo-main">ELLIOTT QUANTUM</div>
        <div class="logo-sub">Control Terminal · Elliott Wave Engine</div>
      </div>
    </div>
    <div class="header-right">
      <div class="live-badge"><div class="live-dot"></div>LIVE</div>
      <div class="sys-tag">LV.4</div>
    </div>
  </div>

  <div class="panel">
    <div class="c1"></div><div class="c2"></div>
    <div class="panel-title">Balance</div>
    <div class="balance">BALANCE_PLACEHOLDER<span class="balance-unit">USDT</span></div>
  </div>

  <div class="panel">
    <div class="c1"></div><div class="c2"></div>
    <div class="panel-title">Active Positions</div>
    POSITION_PLACEHOLDER
  </div>

  <div class="panel">
    <div class="c1"></div><div class="c2"></div>
    <div class="panel-title">Actions</div>
    <form method="POST" action="/dashboard/run">
      <input type="hidden" name="token" value="TOKEN_PLACEHOLDER">
      <button class="run-btn" type="submit">▶ MANUAL RUN</button>
    </form>
  </div>

  <div class="panel">
    <div class="c1"></div><div class="c2"></div>
    <div class="panel-title">System Log</div>
    <pre>LOG_PLACEHOLDER</pre>
  </div>

  <div class="footer">
    <span>ELLIOTT QUANTUM · BINANCE FUTURES · LIVE FEED</span>
    <a href="">⟳ REFRESH</a>
  </div>
</div>
</body>
</html>"""

@app.route("/dashboard", methods=["GET"])
def dashboard():
    token = request.args.get("token", "")
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    if token != expected:
        return "FORBIDDEN - ใส่ ?token=YOUR_TOKEN", 403

    try:
        now = time.time()
        if now - _balance_cache["ts"] > 300:
            _balance_cache["value"] = get_balance()
            _balance_cache["ts"] = now
        balance = f"{_balance_cache['value']:.2f}"
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
            db_pos = _load_position(_key(sym, TIMEFRAME))
            sl = f"{float(db_pos.get('sl',0)):,.4f}" if db_pos else "-"
            tp3 = f"{float(db_pos.get('tp3',0)):,.4f}" if db_pos else "-"
            entry_price = f"{float(p.get('entryPrice',0)):,.4f}"
            direction = p.get("positionSide", "-")
            pos_html += f'<div class="pos-row"><span class="pos-sym">{sym}</span> | {direction} | Entry: {entry_price} | SL: {sl} | TP3: {tp3} | PNL: <span class="pnl-{color}">{pnl:.2f} USDT</span></div>'
        if not pos_html:
            pos_html = '<div class="empty-pos">NO ACTIVE POSITIONS</div>'
    except Exception:
        pos_html = "<p>ดึงข้อมูลไม่ได้</p>"

    try:
        log = subprocess.check_output(
            ["journalctl", "-u", "elliott", "-n", "50", "--no-pager"],
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
    symbol = payload.get("symbol", "").upper()

    # ✅ เช็ค Binance จริงก่อนเปิดซ้ำ
    try:
        real_positions = get_open_positions()
        symbols_open = [p["symbol"] for p in real_positions]
        if symbol in symbols_open:
            print(f"⚠️ [{symbol}] มี position บน Binance อยู่แล้ว ไม่เปิดซ้ำ", flush=True)
            return {"ok": False, "reason": "position already open on Binance"}, 200
    except Exception as e:
        print(f"⚠️ เช็ค Binance ล้มเหลว: {e} — เปิดต่อปกติ", flush=True)

    ok = execute_signal(payload)
    return {"ok": bool(ok)}, 200

@app.route("/position/status", methods=["GET"])
def position_status():
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    got = (request.headers.get("X-EXEC-TOKEN") or "").strip()
    if expected and got != expected:
        return "FORBIDDEN", 403

    symbol = request.args.get("symbol", "").upper()
    if not symbol:
        return {"error": "symbol required"}, 400

    active = get_active(symbol, TIMEFRAME)
    return {"symbol": symbol, "active": active is not None}, 200

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