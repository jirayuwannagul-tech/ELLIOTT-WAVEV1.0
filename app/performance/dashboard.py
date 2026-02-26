# app/performance/dashboard.py
from __future__ import annotations

import os
from flask import Blueprint, request
from app.performance.metrics import compute_metrics

perf_bp = Blueprint("performance", __name__)

PERF_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ELLIOTT QUANTUM — Performance</title>
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

.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:12px}
.kpi{position:relative;background:rgba(0,10,25,0.9);border:1px solid var(--border);border-radius:4px;padding:14px 16px;overflow:hidden;backdrop-filter:blur(10px)}
.kpi::before,.kpi::after,.kpi .c1,.kpi .c2{content:'';position:absolute;width:8px;height:8px;border-color:var(--cyan);border-style:solid;opacity:0.2}
.kpi::before{top:0;left:0;border-width:1px 0 0 1px}
.kpi::after{top:0;right:0;border-width:1px 1px 0 0}
.kpi .c1{bottom:0;left:0;border-width:0 0 1px 1px}
.kpi .c2{bottom:0;right:0;border-width:0 1px 1px 0}
.kpi-bar{position:absolute;top:0;left:0;right:0;height:2px;background:var(--cyan);opacity:0.4}
.kpi-bar.green{background:var(--green)}
.kpi-bar.red{background:var(--red)}
.kpi-bar.yellow{background:var(--yellow)}
.kpi-label{font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:10px}
.kpi-value{font-family:'Share Tech Mono',monospace;font-size:24px;font-weight:700;line-height:1;color:var(--cyan);text-shadow:0 0 15px rgba(0,245,255,0.4)}
.kpi-value.green{color:var(--green);text-shadow:0 0 15px rgba(0,255,157,0.4)}
.kpi-value.red{color:var(--red);text-shadow:0 0 15px rgba(255,23,68,0.4)}
.kpi-value.yellow{color:var(--yellow);text-shadow:0 0 15px rgba(255,234,0,0.4)}

.panels{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
@media(max-width:700px){.panels{grid-template-columns:1fr}}
.chart-wrap{height:130px;position:relative}
canvas{width:100%!important;height:100%!important}

table{width:100%;border-collapse:collapse}
th{color:var(--dim);font-size:9px;text-transform:uppercase;letter-spacing:2px;padding:6px 8px;text-align:left;border-bottom:1px solid var(--border);font-family:'Orbitron',monospace}
td{padding:8px 8px;border-bottom:1px solid rgba(0,245,255,0.04);font-size:11px}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:2px 8px;border-radius:2px;font-size:9px;font-weight:700;letter-spacing:1px;font-family:'Orbitron',monospace}
.pill.win{background:rgba(0,255,157,0.1);color:var(--green);border:1px solid rgba(0,255,157,0.2)}
.pill.loss{background:rgba(255,23,68,0.1);color:var(--red);border:1px solid rgba(255,23,68,0.2)}

.log{max-height:300px;overflow-y:auto}
.log::-webkit-scrollbar{width:3px}
.log::-webkit-scrollbar-thumb{background:var(--dim);border-radius:2px}
.log-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(0,245,255,0.04);gap:8px;flex-wrap:wrap}
.log-row:last-child{border-bottom:none}
.log-sym{font-family:'Orbitron',monospace;font-size:11px;color:var(--cyan);font-weight:700;min-width:100px;text-shadow:0 0 10px rgba(0,245,255,0.3)}
.log-detail{color:var(--text);font-size:10px;flex:1;opacity:0.7;line-height:1.7}
.log-result{font-size:10px;font-weight:700;letter-spacing:1px;font-family:'Orbitron',monospace}
.log-result.tp{color:var(--green);text-shadow:0 0 8px rgba(0,255,157,0.4)}
.log-result.sl{color:var(--red);text-shadow:0 0 8px rgba(255,23,68,0.4)}

.empty{color:var(--dim);text-align:center;padding:32px;font-size:11px;letter-spacing:2px}
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
        <div class="logo-sub">Performance Analytics · Live DB Feed</div>
      </div>
    </div>
    <div class="header-right">
      <div class="live-badge"><div class="live-dot"></div>LIVE</div>
      <div class="sys-tag">PERF</div>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar green"></div>
      <div class="kpi-label">Winrate</div>
      <div class="kpi-value green">WINRATE_VAL%</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar"></div>
      <div class="kpi-label">Total Trades</div>
      <div class="kpi-value">TOTAL_VAL</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar green"></div>
      <div class="kpi-label">Win</div>
      <div class="kpi-value green">WIN_VAL</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar red"></div>
      <div class="kpi-label">Loss</div>
      <div class="kpi-value red">LOSS_VAL</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar yellow"></div>
      <div class="kpi-label">Active</div>
      <div class="kpi-value yellow">ACTIVE_VAL</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar TOTAL_R_CLASS"></div>
      <div class="kpi-label">Total R</div>
      <div class="kpi-value TOTAL_R_CLASS">TOTAL_R_VAL R</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar red"></div>
      <div class="kpi-label">Max Drawdown</div>
      <div class="kpi-value red">MAX_DD_VAL R</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar SHARPE_CLASS"></div>
      <div class="kpi-label">Sharpe Ratio</div>
      <div class="kpi-value SHARPE_CLASS">SHARPE_VAL</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar"></div>
      <div class="kpi-label">Profit Factor</div>
      <div class="kpi-value">PF_VAL</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar"></div>
      <div class="kpi-label">Avg R/Trade</div>
      <div class="kpi-value">AVG_RR_VAL R</div>
    </div>
    <div class="kpi"><div class="c1"></div><div class="c2"></div>
      <div class="kpi-bar TOTAL_PNL_CLASS"></div>
      <div class="kpi-label">Total PnL (USDT)</div>
      <div class="kpi-value TOTAL_PNL_CLASS">TOTAL_PNL_VAL USDT</div>
    </div>
  </div>

  <div class="panels">
    <div class="panel">
      <div class="c1"></div><div class="c2"></div>
      <div class="panel-title">Equity Curve (R)</div>
      <div class="chart-wrap"><canvas id="eqChart"></canvas></div>
    </div>
    <div class="panel">
      <div class="c1"></div><div class="c2"></div>
      <div class="panel-title">Per Symbol</div>
      SYM_TABLE_PLACEHOLDER
    </div>
  </div>

  <div class="panel">
    <div class="c1"></div><div class="c2"></div>
    <div class="panel-title">ประวัติการเทรด (ล่าสุด 30 รายการ)</div>
    <div class="log">LOG_PLACEHOLDER</div>
  </div>

  <div class="footer">
    <span>ELLIOTT QUANTUM · BINANCE FUTURES · LIVE DB</span>
    <a href="">⟳ REFRESH</a>
  </div>
</div>

<script>
const curve = EQUITY_CURVE_JSON;
if (curve.length > 0) {
  const canvas = document.getElementById('eqChart');
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth * window.devicePixelRatio;
  canvas.height = canvas.offsetHeight * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  const W = canvas.offsetWidth, H = canvas.offsetHeight, pad = 10;
  const min = Math.min(...curve, 0), max = Math.max(...curve, 0);
  const range = max - min || 1;
  const toX = i => pad + (i / (curve.length - 1 || 1)) * (W - pad * 2);
  const toY = v => H - pad - ((v - min) / range) * (H - pad * 2);
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(0,245,255,0.15)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4,4]);
  ctx.moveTo(pad, toY(0));
  ctx.lineTo(W - pad, toY(0));
  ctx.stroke();
  ctx.setLineDash([]);
  const lastVal = curve[curve.length - 1];
  const mainColor = lastVal >= 0 ? '#00ff9d' : '#ff1744';
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, mainColor + '44');
  grad.addColorStop(1, mainColor + '00');
  ctx.beginPath();
  curve.forEach((v, i) => i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)));
  ctx.lineTo(toX(curve.length - 1), H);
  ctx.lineTo(toX(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.beginPath();
  ctx.strokeStyle = mainColor;
  ctx.lineWidth = 2;
  ctx.shadowColor = mainColor;
  ctx.shadowBlur = 8;
  curve.forEach((v, i) => i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)));
  ctx.stroke();
}
</script>
</body>
</html>
"""


def _fmt(x: float) -> str:
    x = float(x)
    return f"{x:,.5f}" if x < 1 else f"{x:,.2f}"


@perf_bp.route("/performance", methods=["GET"])
def performance_dashboard():
    expected = (os.getenv("EXEC_TOKEN") or "").strip()
    token = (request.args.get("token") or "").strip()
    if expected and token != expected:
        return "FORBIDDEN", 403

    m = compute_metrics()

    sym_stats = m.get("symbol_stats") or {}
    if sym_stats:
        rows = ""
        for sym, s in sorted(sym_stats.items(), key=lambda x: -x[1]["total"]):
            wr_class = "win" if s["winrate"] >= 50 else "loss"
            rows += f"""<tr>
              <td style="color:rgba(0,245,255,0.8);font-family:'Orbitron',monospace;font-size:10px">{sym}</td>
              <td>{s['total']}</td>
              <td><span class="pill {wr_class}">{s['winrate']}%</span></td>
            </tr>"""
        sym_table = f"""<table>
          <thead><tr><th>Symbol</th><th>Trades</th><th>Winrate</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        sym_table = '<div class="empty">— NO DATA —</div>'

    closed = list(reversed(m.get("closed_positions") or []))[:30]
    if closed:
        log_html = ""
        for p in closed:
            reason = p.get("closed_reason", "?")
            cls = "tp" if reason == "TP3" else "sl"
            label = "✅ TP3" if reason == "TP3" else "❌ SL"
            direction = p.get("direction", "-")
            entry = _fmt(p.get("entry") or 0)
            sl = _fmt(p.get("sl") or 0)
            tp3 = _fmt(p.get("tp3") or 0)
            opened = (p.get("opened_at") or "")[:16].replace("T", " ")
            closed_at = (p.get("closed_at") or "")[:16].replace("T", " ")
            log_html += f"""<div class="log-row">
              <div class="log-sym">{p.get('symbol','-')}</div>
              <div class="log-detail">{direction} | Entry {entry} | SL {sl} | TP3 {tp3}<br>{opened} → {closed_at}</div>
              <div class="log-result {cls}">{label}</div>
            </div>"""
    else:
        log_html = '<div class="empty">— NO TRADE HISTORY —</div>'

    total_r = m["total_r"]
    sharpe = m["sharpe_ratio"]
    total_pnl = m["total_pnl_usdt"]

    html = PERF_HTML
    html = html.replace("WINRATE_VAL", str(m["winrate"]))
    html = html.replace("TOTAL_VAL", str(m["total_closed"]))
    html = html.replace("WIN_VAL", str(m["win_count"]))
    html = html.replace("LOSS_VAL", str(m["loss_count"]))
    html = html.replace("ACTIVE_VAL", str(m["active"]))
    html = html.replace("TOTAL_R_VAL", str(total_r))
    html = html.replace("TOTAL_R_CLASS", "green" if total_r >= 0 else "red")
    html = html.replace("MAX_DD_VAL", str(m["max_drawdown_r"]))
    html = html.replace("SHARPE_VAL", str(sharpe))
    html = html.replace("SHARPE_CLASS", "green" if sharpe >= 1 else ("yellow" if sharpe >= 0 else "red"))
    html = html.replace("PF_VAL", str(m["profit_factor"]))
    html = html.replace("AVG_RR_VAL", str(m["avg_rr"]))
    html = html.replace("TOTAL_PNL_VAL", str(total_pnl))
    html = html.replace("TOTAL_PNL_CLASS", "green" if total_pnl >= 0 else "red")
    html = html.replace("SYM_TABLE_PLACEHOLDER", sym_table)
    html = html.replace("LOG_PLACEHOLDER", log_html)
    html = html.replace("EQUITY_CURVE_JSON", str(m["equity_curve"]))

    return html