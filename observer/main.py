import json
import os
from datetime import datetime, timezone

from flask import Flask, jsonify
from google.api_core.exceptions import PermissionDenied
from google.cloud import firestore

app = Flask(__name__)
db = firestore.Client()

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "cs323-voting-system-pwedesi")
COLLECTION_NAME = os.environ.get("FIRESTORE_COLLECTION", "votes")


def _format_latency(value):
    if value is None:
        return ""
    try:
        return f"{float(value):.3f} ms"
    except (TypeError, ValueError):
        return str(value)


def _collect_latency(votes, field_name):
    values = []
    for vote in votes:
        raw_value = vote.get(field_name)
        if raw_value is None:
            continue
        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            values.append(parsed)
    return values


def _resolve_worker_latency(vote):
    for field_name in ("worker_total_ms", "cloud_latency_ms"):
        raw_value = vote.get(field_name)
        if raw_value is None:
            continue
        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _load_votes():
    docs = db.collection(COLLECTION_NAME).stream()
    votes = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["doc_id"] = doc.id
        votes.append(data)
    return votes


def _load_votes_safe():
    try:
        return _load_votes(), None
    except PermissionDenied as exc:
        return [], str(exc)


def _latency_stats(values):
    if not values:
        return {"count": 0, "avg_ms": None, "min_ms": None, "max_ms": None}
    return {
        "count": len(values),
        "avg_ms": round(sum(values) / len(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def _summarize_votes(votes):
    choice_counts = {}
    edge_counts = {}
    worker_latencies = []
    firestore_write_latencies = _collect_latency(votes, "firestore_write_ms")

    for vote in votes:
        choice = str(vote.get("choice", "unknown"))
        edge_id = str(vote.get("edge_id", "unknown"))
        choice_counts[choice] = choice_counts.get(choice, 0) + 1
        edge_counts[edge_id] = edge_counts.get(edge_id, 0) + 1

        worker_latency = _resolve_worker_latency(vote)
        if worker_latency is not None:
            worker_latencies.append(worker_latency)

    choice_sorted = sorted(choice_counts.items(), key=lambda item: (-item[1], item[0]))
    edge_sorted = sorted(edge_counts.items(), key=lambda item: (-item[1], item[0]))

    return {
        "project_id": PROJECT_ID,
        "collection_name": COLLECTION_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_votes": len(votes),
        "unique_edges": sorted(edge_counts.keys()),
        "choice_counts": choice_sorted,
        "edge_counts": edge_sorted,
        "chart_labels": {
            "choices": [label for label, _ in choice_sorted],
            "edges": [label for label, _ in edge_sorted],
        },
        "chart_values": {
            "choices": [count for _, count in choice_sorted],
            "edges": [count for _, count in edge_sorted],
        },
        "latency_stats": {
            "worker": _latency_stats(worker_latencies),
            "firestore_write": _latency_stats(firestore_write_latencies),
        },
    }


@app.route("/")
def dashboard():
    votes, load_error = _load_votes_safe()
    summary = _summarize_votes(votes)

    choice_items = "".join(
        f"<li><strong>{choice}</strong>: {count}</li>" for choice, count in summary["choice_counts"]
    ) or "<li>No votes yet</li>"
    edge_items = "".join(
        f"<li><strong>{edge}</strong>: {count}</li>" for edge, count in summary["edge_counts"]
    ) or "<li>No votes yet</li>"

    html = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Vote Observer</title>
      <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
      <style>
        :root {{
          --bg: #0b1020;
          --text: #eaf0ff;
          --muted: #98a6c7;
          --border: rgba(255,255,255,0.08);
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: radial-gradient(circle at top left, rgba(77,208,225,0.14), transparent 28%),
                      radial-gradient(circle at top right, rgba(142,125,255,0.12), transparent 24%),
                      var(--bg);
          color: var(--text);
        }}
        .wrap {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 56px; }}
        header {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: end; margin-bottom: 24px; }}
        h1 {{ margin: 0; font-size: 2rem; letter-spacing: -0.03em; }}
        .sub {{ color: var(--muted); margin-top: 8px; }}
        .pill {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 999px; background: rgba(255,255,255,0.04); color: var(--muted); }}
        .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin: 20px 0; }}
        .card {{ background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)); border: 1px solid var(--border); border-radius: 18px; padding: 18px; box-shadow: 0 12px 40px rgba(0,0,0,0.22); }}
        .metric {{ font-size: 2rem; font-weight: 700; margin-top: 10px; }}
        .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }}
        @media (max-width: 860px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
        h2 {{ margin: 0 0 12px; font-size: 1.05rem; }}
        ul {{ margin: 0; padding-left: 18px; color: var(--muted); }}
        .muted {{ color: var(--muted); }}
        .note {{ margin-top: 8px; color: var(--muted); font-size: 0.92rem; }}
        .error {{ margin: 18px 0 0; padding: 14px 16px; border-radius: 14px; border: 1px solid rgba(255, 122, 122, 0.35); background: rgba(255, 122, 122, 0.08); color: #ffd7d7; }}
        .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-top: 16px; }}
        .chart-wrap {{ position: relative; height: 320px; }}
        .small {{ font-size: 0.88rem; color: var(--muted); }}
        .latency-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <header>
          <div>
            <h1>Vote Observer</h1>
          </div>
        </header>

        <div class="grid">
          <div class="card"><div class="muted">Total votes</div><div class="metric" id="totalVotes">{summary['total_votes']}</div></div>
          <div class="card"><div class="muted">Unique edge nodes</div><div class="metric" id="uniqueEdges">{len(summary['unique_edges'])}</div></div>
          <div class="card"><div class="muted">Choices seen</div><div class="metric" id="choicesSeen">{len(summary['choice_counts'])}</div></div>
        </div>

        <div class="card">
          <h2>Latency benchmark</h2>
          <div class="note">These are service-local durations, so they do not depend on edge-clock alignment.</div>
          <div class="latency-grid">
            <div class="card">
              <div class="muted">Worker total average</div>
              <div class="metric" id="avgWorker">{_format_latency(summary['latency_stats']['worker']['avg_ms'])}</div>
              <div class="small">Min: <span id="minWorker">{_format_latency(summary['latency_stats']['worker']['min_ms'])}</span> · Max: <span id="maxWorker">{_format_latency(summary['latency_stats']['worker']['max_ms'])}</span></div>
            </div>
            <div class="card">
              <div class="muted">Firestore write average</div>
              <div class="metric" id="avgFirestoreWrite">{_format_latency(summary['latency_stats']['firestore_write']['avg_ms'])}</div>
              <div class="small">Min: <span id="minFirestoreWrite">{_format_latency(summary['latency_stats']['firestore_write']['min_ms'])}</span> · Max: <span id="maxFirestoreWrite">{_format_latency(summary['latency_stats']['firestore_write']['max_ms'])}</span></div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>Live vote breakdown</h2>
          <div class="small">The charts below auto-refresh every 5 seconds by polling <code>/api/summary</code>. This is live polling, not websocket push.</div>
          <div class="chart-grid">
            <div class="card"><h2>Votes by Choice</h2><div class="chart-wrap"><canvas id="choiceChart"></canvas></div></div>
            <div class="card"><h2>Votes by Edge</h2><div class="chart-wrap"><canvas id="edgeChart"></canvas></div></div>
          </div>
        </div>

        {f'<div class="error"><strong>Firestore access denied.</strong> {load_error}</div>' if load_error else ''}

      </div>
      <script>
        const loadError = {json.dumps(load_error)};
        const choiceCtx = document.getElementById('choiceChart');
        const edgeCtx = document.getElementById('edgeChart');

        const chartColors = ['#4dd0e1', '#8e7dff', '#ffb86b', '#7ee081', '#ff6b8b', '#a6e3a1', '#ffd166', '#6ec6ff'];

        function makeDoughnut(ctx, labels, values, title) {{
          if (!ctx) return null;
          return new Chart(ctx, {{
            type: 'doughnut',
            data: {{ labels, datasets: [{{ label: title, data: values, backgroundColor: labels.map((_, index) => chartColors[index % chartColors.length]), borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1 }}] }},
            options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#eaf0ff' }} }} }} }},
          }});
        }}

        function makeBar(ctx, labels, values, title) {{
          if (!ctx) return null;
          return new Chart(ctx, {{
            type: 'bar',
            data: {{ labels, datasets: [{{ label: title, data: values, backgroundColor: '#8e7dff', borderRadius: 10 }}] }},
            options: {{
              responsive: true,
              maintainAspectRatio: false,
              scales: {{
                x: {{ ticks: {{ color: '#98a6c7' }}, grid: {{ color: 'rgba(255,255,255,0.06)' }} }},
                y: {{ beginAtZero: true, ticks: {{ color: '#98a6c7', precision: 0 }}, grid: {{ color: 'rgba(255,255,255,0.06)' }} }},
              }},
              plugins: {{ legend: {{ display: false }} }},
            }},
          }});
        }}

        function renderList(items, emptyLabel) {{
          if (!items || items.length === 0) return `<li>${{emptyLabel}}</li>`;
          return items.map(([label, count]) => `<li><strong>${{label}}</strong>: ${{count}}</li>`).join('');
        }}

        function renderSummary(data) {{
          const totalVotes = document.getElementById('totalVotes');
          const uniqueEdges = document.getElementById('uniqueEdges');
          const choicesSeen = document.getElementById('choicesSeen');
          const avgWorker = document.getElementById('avgWorker');
          const minWorker = document.getElementById('minWorker');
          const maxWorker = document.getElementById('maxWorker');
          const avgFirestoreWrite = document.getElementById('avgFirestoreWrite');
          const minFirestoreWrite = document.getElementById('minFirestoreWrite');
          const maxFirestoreWrite = document.getElementById('maxFirestoreWrite');
          const choiceList = document.getElementById('choiceList');
          const edgeList = document.getElementById('edgeList');

          if (totalVotes) totalVotes.textContent = data.total_votes;
          if (uniqueEdges) uniqueEdges.textContent = data.unique_edges.length;
          if (choicesSeen) choicesSeen.textContent = data.chart_labels.choices.length;
          if (avgWorker) avgWorker.textContent = data.latency_stats.worker.avg_ms !== null ? `${{data.latency_stats.worker.avg_ms.toFixed(3)}} ms` : 'No data';
          if (minWorker) minWorker.textContent = data.latency_stats.worker.min_ms !== null ? `${{data.latency_stats.worker.min_ms.toFixed(3)}} ms` : 'No data';
          if (maxWorker) maxWorker.textContent = data.latency_stats.worker.max_ms !== null ? `${{data.latency_stats.worker.max_ms.toFixed(3)}} ms` : 'No data';
          if (avgFirestoreWrite) avgFirestoreWrite.textContent = data.latency_stats.firestore_write.avg_ms !== null ? `${{data.latency_stats.firestore_write.avg_ms.toFixed(3)}} ms` : 'No data';
          if (minFirestoreWrite) minFirestoreWrite.textContent = data.latency_stats.firestore_write.min_ms !== null ? `${{data.latency_stats.firestore_write.min_ms.toFixed(3)}} ms` : 'No data';
          if (maxFirestoreWrite) maxFirestoreWrite.textContent = data.latency_stats.firestore_write.max_ms !== null ? `${{data.latency_stats.firestore_write.max_ms.toFixed(3)}} ms` : 'No data';
          if (choiceList) choiceList.innerHTML = renderList(data.choice_counts, 'No votes yet');
          if (edgeList) edgeList.innerHTML = renderList(data.edge_counts, 'No votes yet');
        }}

        let choiceChart = makeDoughnut(choiceCtx, {json.dumps([label for label, _ in summary['choice_counts']])}, {json.dumps([count for _, count in summary['choice_counts']])}, 'Votes by Choice');
        let edgeChart = makeBar(edgeCtx, {json.dumps([label for label, _ in summary['edge_counts']])}, {json.dumps([count for _, count in summary['edge_counts']])}, 'Votes by Edge');

        async function refreshSummary() {{
          try {{
            const response = await fetch('/api/summary', {{ cache: 'no-store' }});
            if (!response.ok) {{
              if (response.status === 403) return;
              throw new Error(`HTTP ${{response.status}}`);
            }}
            const data = await response.json();
            document.title = `Vote Observer · ${{data.total_votes}} votes`;
            renderSummary(data);
            if (choiceChart) {{
              choiceChart.data.labels = data.chart_labels.choices;
              choiceChart.data.datasets[0].data = data.chart_values.choices;
              choiceChart.data.datasets[0].backgroundColor = data.chart_labels.choices.map((_, index) => chartColors[index % chartColors.length]);
              choiceChart.update();
            }}
            if (edgeChart) {{
              edgeChart.data.labels = data.chart_labels.edges;
              edgeChart.data.datasets[0].data = data.chart_values.edges;
              edgeChart.update();
            }}
          }} catch (error) {{
            console.warn('Failed to refresh summary', error);
          }}
        }}

        renderSummary({json.dumps(summary)});
        if (!loadError) setInterval(refreshSummary, 5000);
      </script>
    </body>
    </html>
    """
    return html


@app.route("/api/summary")
def api_summary():
    votes, load_error = _load_votes_safe()
    if load_error:
        return jsonify({"error": "firestore_access_denied", "details": load_error}), 403
    return jsonify(_summarize_votes(votes))


@app.route("/healthz")
def healthz():
    return {"status": "ok", "service": "vote-observer"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
