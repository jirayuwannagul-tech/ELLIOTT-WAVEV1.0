# app/performance/dashboard.py
# เพิ่มไฟล์ใหม่ ไม่แตะไฟล์เดิม
# วิธีใช้: import แล้ว register blueprint ใน app/main.py
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
<title>Elliott Wave — Performance</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&family=IBM+Plex+Sans+Thai:wght@300;400;600&display=swap');

  :root {
    --bg: #060a0f;
    --panel: #0d1520;
    --border: #1a2840;
    --accent: #00c8ff;
    --green: #00ff88;
    --red: #ff3c5a;
    --yellow: #ffd700;
    --text: #c8d8e8;
    --dim: #4a6080;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    min-height: 100vh;
    padding: 24px;
  }

  /* grid noise bg */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(0,200,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,200,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .wrap { position: relative; z-index: 1; max-width: 1100px; margin: 0 auto; }

  header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 32px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px;
  }

  header h1 {
    font-size: 22px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.5px;
  }

  header span { color: var(--dim); font-size: 11px; }

  /* KPI grid */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }

  .kpi {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
  }

  .kpi::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
    opacity: 0.4;
  }

  .kpi.green::after { background: var(--green); }
  .kpi.red::after { background: var(--red); }
  .kpi.yellow::after { background: var(--yellow); }

  .kpi-label { color: var(--dim); font-size: 10px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
  .kpi-value { font-size: 26px; font-weight: 600; line-height: 1; }
  .kpi-value.green { color: var(--green); }
  .kpi-value.red { color: var(--red); }
  .kpi-value.yellow { color: var(--yellow); }
  .kpi-value.accent { color: var(--accent); }

  /* panels */
  .panels { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }

  @media (max-width: 700px) { .panels { grid-template-columns: 1fr; } }

  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
  }

  .panel-title {
    color: var(--dim);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }

  /* equity chart */
  .chart-wrap { height: 120px; position: relative; }

  canvas { width: 100% !important; height: 100% !important; }

  /* symbol table */
  table { width: 100%; border-collapse: collapse; }
  th { color: var(--dim); font-size: 10px; text-transform: uppercase; letter-spacing: 1px; padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--border); }
  td { padding: 8px 8px; border-bottom: 1px solid rgba(26,40,64,0.5); font-size: 12px; }
  tr:last-child td { border-bottom: none; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: 600; }
  .pill.win { background: rgba(0,255,136,0.15); color: var(--green); }
  .pill.loss { background: rgba(255,60,90,0.15); color: var(--red); }

  /* positions log */
  .log { max-height: 280px; overflow-y: auto; }
  .log-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(26,40,64,0.5);
    gap: 8px;
    flex-wrap: wrap;
  }
  .log-row:last-child { border-bottom: none; }
  .log-sym { color: var(--accent); font-weight: 600; font-size: 12px; min-width: 90px; }
  .log-detail { color: var(--dim); font-size: 11px; flex: 1; }
  .log-result { font-size: 11px; font-weight: 600; }
  .log-result.tp { color: var(--green); }
  .log-result.sl { color: var(--red); }

  .empty { color: var(--dim); text-align: center; padding: 32px; font-size: 12px; }

  .refresh-note { color: var(--dim); font-size: 10px; margin-top: 16px; text-align: right; }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <h1>🌊 Elliott Wave — Performance</h1>
    <span>Live จาก DB | ไม่ใช่ Backtest</span>
  </header>

  <!-- KPI -->
  <div class="kpi-grid">
    <div class="kpi green">
      <div class="kpi-label">Winrate</div>
      <div class="kpi-value green">WINRATE_VAL%</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Total Trades</div>
      <div class="kpi-value accent">TOTAL_VAL</div>
    </div>
    <div class="kpi green">
      <div class="kpi-label">Win</div>
      <div class="kpi-value green">WIN_VAL</div>
    </div>
    <div class="kpi red">
      <div class="kpi-label">Loss</div>
      <div class="kpi-value red">LOSS_VAL</div>
    </div>
    <div class="kpi yellow">
      <div class="kpi-label">Active</div>
      <div class="kpi-value yellow">ACTIVE_VAL</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Total R</div>
      <div class="kpi-value TOTAL_R_CLASS">TOTAL_R_VAL R</div>
    </div>
    <div class="kpi red">
      <div class="kpi-label">Max Drawdown</div>
      <div class="kpi-value red">MAX_DD_VAL R</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Sharpe Ratio</div>
      <div class="kpi-value SHARPE_CLASS">SHARPE_VAL</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Profit Factor</div>
      <div class="kpi-value accent">PF_VAL</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Avg R/Trade</div>
      <div class="kpi-value accent">AVG_RR_VAL R</div>
    </div>
  </div>

  <!-- Chart + Symbol Table -->
  <div class="panels">
    <div class="panel">
      <div class="panel-title">Equity Curve (R)</div>
      <div class="chart-wrap">
        <canvas id="eqChart"></canvas>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">Per Symbol</div>
      SYM_TABLE_PLACEHOLDER
    </div>
  </div>

  <!-- Closed positions log -->
  <div class="panel">
    <div class="panel-title">ประวัติการเทรด (ล่าสุด 30 รายการ)</div>
    <div class="log">
      LOG_PLACEHOLDER
    </div>
  </div>

  <div class="refresh-note">🔄 <a href="" style="color:var(--dim)">รีเฟรช</a></div>

</div>

<script>
const curve = EQUITY_CURVE_JSON;

if (curve.length > 0) {
  const canvas = document.getElementById('eqChart');
  const ctx = canvas.getContext('2d');

  canvas.width = canvas.offsetWidth * window.devicePixelRatio;
  canvas.height = canvas.offsetHeight * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  const W = canvas.offsetWidth;
  const H = canvas.offsetHeight;
  const pad = 8;

  const min = Math.min(...curve, 0);
  const max = Math.max(...curve, 0);
  const range = max - min || 1;

  const toX = i => pad + (i / (curve.length - 1 || 1)) * (W - pad * 2);
  const toY = v => H - pad - ((v - min) / range) * (H - pad * 2);

  // zero line
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(74,96,128,0.5)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  const zeroY = toY(0);
  ctx.moveTo(pad, zeroY);
  ctx.lineTo(W - pad, zeroY);
  ctx.stroke();
  ctx.setLineDash([]);

  // fill
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  const lastVal = curve[curve.length - 1];
  const mainColor = lastVal >= 0 ? '#00ff88' : '#ff3c5a';
  grad.addColorStop(0, mainColor + '33');
  grad.addColorStop(1, mainColor + '00');

  ctx.beginPath();
  curve.forEach((v, i) => {
    i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v));
  });
  ctx.lineTo(toX(curve.length - 1), H);
  ctx.lineTo(toX(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // line
  ctx.beginPath();
  ctx.strokeStyle = mainColor;
  ctx.lineWidth = 2;
  curve.forEach((v, i) => {
    i === 0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v));
  });
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

    # Symbol table
    sym_stats = m.get("symbol_stats") or {}
    if sym_stats:
        rows = ""
        for sym, s in sorted(sym_stats.items(), key=lambda x: -x[1]["total"]):
            wr_class = "win" if s["winrate"] >= 50 else "loss"
            rows += f"""<tr>
              <td>{sym}</td>
              <td>{s['total']}</td>
              <td><span class="pill {wr_class}">{s['winrate']}%</span></td>
            </tr>"""
        sym_table = f"""<table>
          <thead><tr><th>Symbol</th><th>Trades</th><th>Winrate</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        sym_table = '<div class="empty">ยังไม่มีข้อมูล</div>'

    # Log
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
        log_html = '<div class="empty">ยังไม่มีประวัติการเทรด</div>'

    # Render
    total_r = m["total_r"]
    sharpe = m["sharpe_ratio"]

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
    html = html.replace("SYM_TABLE_PLACEHOLDER", sym_table)
    html = html.replace("LOG_PLACEHOLDER", log_html)
    html = html.replace("EQUITY_CURVE_JSON", str(m["equity_curve"]))

    return html