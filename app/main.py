from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # must run before langfuse is imported

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
app = FastAPI(title="Day 13 Observability Lab")
app.add_middleware(CorrelationIdMiddleware)
agent = LabAgent()


@app.on_event("shutdown")
async def shutdown() -> None:
    from .tracing import tracing_enabled
    if tracing_enabled():
        try:
            from langfuse import Langfuse
            Langfuse().flush()
        except Exception:
            pass


@app.on_event("startup")
async def startup() -> None:
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-observability-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Observability Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e0e0e0; padding: 16px; }
  h1 { font-size: 1.2rem; margin-bottom: 4px; }
  #meta { font-size: 0.75rem; color: #888; margin-bottom: 16px; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .panel { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 14px; }
  .panel h2 { font-size: 0.8rem; font-weight: 600; color: #aaa; text-transform: uppercase;
              letter-spacing: .05em; margin-bottom: 10px; }
  .stat { font-size: 2rem; font-weight: 700; color: #fff; line-height: 1; }
  .stat-sub { font-size: 0.7rem; color: #666; margin-top: 4px; }
  .slo-badge { display: inline-block; font-size: 0.65rem; padding: 2px 6px; border-radius: 10px;
               margin-top: 8px; }
  .ok  { background:#1a3a2a; color:#4caf50; }
  .warn{ background:#3a2a1a; color:#ff9800; }
  .bad { background:#3a1a1a; color:#f44336; }
  canvas { max-height: 130px; }
  @media(max-width:800px){ .grid{ grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>
<h1>Observability Dashboard</h1>
<p id="meta">Auto-refresh every 20s &nbsp;|&nbsp; Time range: since app start &nbsp;|&nbsp; <span id="last-updated">loading…</span></p>
<div class="grid">
  <!-- Panel 1: Latency -->
  <div class="panel">
    <h2>Latency P50 / P95 / P99 (ms)</h2>
    <canvas id="latencyChart"></canvas>
    <span id="latency-slo" class="slo-badge">SLO: P95 &lt; 5000 ms</span>
  </div>
  <!-- Panel 2: Traffic -->
  <div class="panel">
    <h2>Traffic</h2>
    <div class="stat" id="traffic-val">—</div>
    <div class="stat-sub">total requests</div>
  </div>
  <!-- Panel 3: Error rate -->
  <div class="panel">
    <h2>Error Rate &amp; Breakdown</h2>
    <div class="stat" id="error-rate-val">—</div>
    <div class="stat-sub" id="error-breakdown">no errors</div>
  </div>
  <!-- Panel 4: Cost -->
  <div class="panel">
    <h2>Cost (USD)</h2>
    <div class="stat" id="cost-val">—</div>
    <div class="stat-sub" id="cost-sub">avg per request</div>
    <span id="cost-slo" class="slo-badge ok">SLO: avg &lt; $0.01</span>
  </div>
  <!-- Panel 5: Tokens In / Out -->
  <div class="panel">
    <h2>Tokens In / Out</h2>
    <canvas id="tokenChart"></canvas>
  </div>
  <!-- Panel 6: Quality -->
  <div class="panel">
    <h2>Quality Score (avg)</h2>
    <div class="stat" id="quality-val">—</div>
    <div class="stat-sub">heuristic proxy 0–1</div>
    <span id="quality-slo" class="slo-badge ok">SLO: avg &ge; 0.6</span>
  </div>
</div>

<script>
const SLO_LATENCY_P95 = 5000;
const SLO_COST_AVG    = 0.01;
const SLO_QUALITY_MIN = 0.6;

function badge(el, ok, warn, msg) {
  el.textContent = msg;
  el.className = 'slo-badge ' + (ok ? 'ok' : warn ? 'warn' : 'bad');
}

const latencyChart = new Chart(document.getElementById('latencyChart'), {
  type: 'bar',
  data: {
    labels: ['P50', 'P95', 'P99'],
    datasets: [{
      label: 'ms',
      data: [0, 0, 0],
      backgroundColor: ['#4caf50', '#ff9800', '#f44336'],
      borderRadius: 4,
    }]
  },
  options: {
    plugins: {
      legend: { display: false },
      annotation: {}
    },
    scales: {
      y: { ticks: { color: '#888' }, grid: { color: '#222' } },
      x: { ticks: { color: '#888' }, grid: { display: false } }
    }
  }
});

const tokenChart = new Chart(document.getElementById('tokenChart'), {
  type: 'bar',
  data: {
    labels: ['Tokens In', 'Tokens Out'],
    datasets: [{
      label: 'total',
      data: [0, 0],
      backgroundColor: ['#2196f3', '#9c27b0'],
      borderRadius: 4,
    }]
  },
  options: {
    plugins: { legend: { display: false } },
    scales: {
      y: { ticks: { color: '#888' }, grid: { color: '#222' } },
      x: { ticks: { color: '#888' }, grid: { display: false } }
    }
  }
});

async function refresh() {
  try {
    const r  = await fetch('/metrics');
    const m  = await r.json();

    // Panel 1 – Latency
    latencyChart.data.datasets[0].data = [m.latency_p50, m.latency_p95, m.latency_p99];
    latencyChart.update();
    const latOk = m.latency_p95 <= SLO_LATENCY_P95;
    badge(document.getElementById('latency-slo'), latOk, false,
          'SLO: P95 < 5000ms — ' + (latOk ? '✓ OK' : '✗ BREACH') + ' (' + m.latency_p95 + 'ms)');

    // Panel 2 – Traffic
    document.getElementById('traffic-val').textContent = m.traffic;

    // Panel 3 – Error rate
    const total = m.traffic || 1;
    const errCount = Object.values(m.error_breakdown || {}).reduce((a, b) => a + b, 0);
    const errPct = ((errCount / total) * 100).toFixed(1);
    const errEl = document.getElementById('error-rate-val');
    errEl.textContent = errPct + '%';
    errEl.style.color = errCount === 0 ? '#4caf50' : errPct > 5 ? '#f44336' : '#ff9800';
    const breakdown = Object.entries(m.error_breakdown || {});
    document.getElementById('error-breakdown').textContent =
      breakdown.length ? breakdown.map(([k,v]) => k + ': ' + v).join(', ') : 'no errors';

    // Panel 4 – Cost
    document.getElementById('cost-val').textContent = '$' + m.total_cost_usd.toFixed(4);
    document.getElementById('cost-sub').textContent = 'avg $' + m.avg_cost_usd + ' per request';
    const costOk = m.avg_cost_usd <= SLO_COST_AVG;
    badge(document.getElementById('cost-slo'), costOk, false,
          'SLO: avg < $0.01 — ' + (costOk ? '✓ OK' : '✗ BREACH'));

    // Panel 5 – Tokens
    tokenChart.data.datasets[0].data = [m.tokens_in_total, m.tokens_out_total];
    tokenChart.update();

    // Panel 6 – Quality
    const qEl = document.getElementById('quality-val');
    qEl.textContent = m.quality_avg;
    const qOk = m.quality_avg >= SLO_QUALITY_MIN;
    badge(document.getElementById('quality-slo'), qOk, m.quality_avg >= 0.5,
          'SLO: avg ≥ 0.6 — ' + (qOk ? '✓ OK' : '✗ BREACH') + ' (' + m.quality_avg + ')');

    document.getElementById('last-updated').textContent =
      'last updated: ' + new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById('last-updated').textContent = 'fetch error: ' + e.message;
  }
}

refresh();
setInterval(refresh, 20000);
</script>
</body>
</html>"""


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )

    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
        )
        log.info(
            "response_sent",
            service="api",
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=result.latency_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str) -> JSONResponse:
    try:
        enable(name)
        log.warning("incident_enabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str) -> JSONResponse:
    try:
        disable(name)
        log.warning("incident_disabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
