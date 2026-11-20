"""Run RAG benchmark and render an interactive HTML dashboard.

Usage (from services/api):
  python -m eval.rag_visualize
  # Dev-only dashboard from local rag_benchmark JSON (not used in official LangSmith reports).
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .corpus_loader import EVAL_DIR, missing_corpus_paths
from .rag_benchmark import DEFAULT_GOLD, DEFAULT_OUT, run_benchmark

DEFAULT_HTML = EVAL_DIR / 'out' / 'rag-benchmark-dashboard.html'


def _load_gold_cases() -> dict[str, dict]:
    raw = json.loads(DEFAULT_GOLD.read_text(encoding='utf-8'))
    return {c['id']: c for c in raw.get('cases', [])}


def _kind_metrics(cases: list[dict]) -> dict[str, dict]:
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for row in cases:
        by_kind[row['kind']].append(row)
    out = {}
    for kind, rows in sorted(by_kind.items()):
        n = len(rows)
        passed = sum(1 for r in rows if r.get('passed'))
        out[kind] = {
            'n': n,
            'pass_rate': passed / n if n else 0,
            'retrieval': sum(1 for r in rows if r.get('retrieval_hit')) / n if n else 0,
            'evidence': sum(1 for r in rows if r.get('evidence_support')) / n if n else 0,
        }
    return out


def render_html(report: dict, gold_meta: dict[str, dict]) -> str:
    m = report['metrics']
    cases = report['cases']
    kinds = _kind_metrics(cases)
    modes = Counter(c.get('mode') or '?' for c in cases)
    fails = [c for c in cases if not c.get('passed')]

    metric_labels = [
        'pass_rate', 'retrieval_hit_rate', 'evidence_support_rate',
        'refusal_accuracy', 'in_scope_pass_rate', 'paraphrase_pass_rate',
        'compare_pass_rate', 'multi_hop_pass_rate', 'answer_all_rate', 'answer_clean_rate',
    ]
    metric_vals = [round(float(m.get(k, 0) or 0) * 100, 1) for k in metric_labels]
    metric_pretty = [k.replace('_', ' ') for k in metric_labels]

    kind_labels = list(kinds.keys())
    kind_pass = [round(kinds[k]['pass_rate'] * 100, 1) for k in kind_labels]
    kind_n = [kinds[k]['n'] for k in kind_labels]

    mode_labels = list(modes.keys())
    mode_counts = [modes[k] for k in mode_labels]

    rows_html = []
    for c in cases:
        meta = gold_meta.get(c['id'], {})
        docs = meta.get('documents') or report.get('corpus') or []
        if isinstance(docs, list) and docs and isinstance(docs[0], str) and docs[0].startswith('corpus/'):
            scope = 'all'
        elif isinstance(docs, list):
            scope = ', '.join(docs)
        else:
            scope = str(docs)
        status = 'pass' if c.get('passed') else 'fail'
        rows_html.append(
            f'<tr class="{status}">'
            f'<td><code>{c["id"]}</code></td>'
            f'<td>{c["kind"]}</td>'
            f'<td class="scope">{scope}</td>'
            f'<td><span class="badge {"ok" if c.get("passed") else "bad"}">'
            f'{"PASS" if c.get("passed") else "FAIL"}</span></td>'
            f'<td><code>{c.get("mode")}</code></td>'
            f'<td class="bool">{_icon(c.get("retrieval_hit"))}</td>'
            f'<td class="bool">{_icon(c.get("evidence_support"))}</td>'
            f'<td class="bool">{_icon(c.get("answer_all"))}</td>'
            f'<td class="notes">{c.get("notes") or ""}</td>'
            f'<td class="q">{_esc(c.get("question", "")[:120])}</td>'
            f'</tr>'
        )

    corpus = report.get('corpus')
    if isinstance(corpus, list):
        corpus_line = ', '.join(corpus)
    else:
        corpus_line = str(corpus)

    generated = report.get('generated_at') or datetime.now(timezone.utc).isoformat()
    suite = report.get('name') or 'rag'

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>RAG benchmark — {suite}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419; --card: #1a2332; --text: #e7ecf3; --muted: #94a3b8;
      --ok: #34d399; --bad: #f87171; --accent: #60a5fa; --border: #2d3a4f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.5;
    }}
    header {{ padding: 1.5rem 2rem; border-bottom: 1px solid var(--border); }}
    h1 {{ margin: 0 0 .35rem; font-size: 1.5rem; font-weight: 600; }}
    .sub {{ color: var(--muted); font-size: .9rem; }}
    main {{ padding: 1.25rem 2rem 2.5rem; max-width: 1400px; margin: 0 auto; }}
    .grid {{ display: grid; gap: 1.25rem; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
    .card {{
      background: var(--card); border: 1px solid var(--border); border-radius: 12px;
      padding: 1rem 1.15rem;
    }}
    .card h2 {{ margin: 0 0 .75rem; font-size: 1rem; color: var(--muted); font-weight: 600; }}
    .kpi {{ display: flex; flex-wrap: wrap; gap: .75rem; }}
    .kpi div {{
      flex: 1 1 120px; padding: .75rem; background: #121a26; border-radius: 8px;
      border: 1px solid var(--border);
    }}
  .kpi .val {{ font-size: 1.75rem; font-weight: 700; color: var(--accent); }}
  .kpi .lbl {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
    th, td {{ padding: .45rem .5rem; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; position: sticky; top: 0; background: var(--card); }}
    tr.fail {{ background: rgba(248, 113, 113, .08); }}
    .badge {{ font-size: .7rem; padding: .15rem .45rem; border-radius: 4px; font-weight: 600; }}
    .badge.ok {{ background: rgba(52, 211, 153, .2); color: var(--ok); }}
    .badge.bad {{ background: rgba(248, 113, 113, .2); color: var(--bad); }}
    .bool {{ text-align: center; }}
    .scope {{ color: var(--muted); font-size: .78rem; }}
    .q {{ color: var(--muted); max-width: 280px; }}
    .table-wrap {{ overflow: auto; max-height: 520px; border-radius: 8px; border: 1px solid var(--border); }}
    canvas {{ max-height: 280px; }}
  </style>
</head>
<body>
  <header>
    <h1>RAG benchmark dashboard</h1>
    <p class="sub">Suite <strong>{_esc(suite)}</strong> · {m.get('n', len(cases))} cases ·
    offline (local embedding) · generated { _esc(generated) }</p>
    <p class="sub">Corpus: {_esc(corpus_line)}</p>
  </header>
  <main>
    <div class="kpi card" style="margin-bottom:1.25rem">
      <h2>Summary</h2>
      <div class="kpi">
        <div><div class="val">{metric_vals[0]:.0f}%</div><div class="lbl">Overall pass</div></div>
        <div><div class="val">{metric_vals[1]:.0f}%</div><div class="lbl">Retrieval hit</div></div>
        <div><div class="val">{metric_vals[2]:.0f}%</div><div class="lbl">Evidence</div></div>
        <div><div class="val">{metric_vals[3]:.0f}%</div><div class="lbl">Refusal (off-topic)</div></div>
        <div><div class="val">{len(fails)}</div><div class="lbl">Failures</div></div>
      </div>
    </div>
    <div class="grid">
      <div class="card"><h2>Aggregate metrics (%)</h2><canvas id="metricsChart"></canvas></div>
      <div class="card"><h2>Pass rate by kind</h2><canvas id="kindChart"></canvas></div>
      <div class="card"><h2>Answer modes</h2><canvas id="modeChart"></canvas></div>
    </div>
    <div class="card" style="margin-top:1.25rem">
      <h2>Per-case results</h2>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>ID</th><th>Kind</th><th>Scope</th><th>Pass</th><th>Mode</th>
            <th>Retrieval</th><th>Evidence</th><th>All cues</th><th>Notes</th><th>Question</th>
          </tr></thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
      </div>
    </div>
  </main>
  <script>
    const metricLabels = {json.dumps(metric_pretty, ensure_ascii=False)};
    const metricData = {json.dumps(metric_vals)};
    new Chart(document.getElementById('metricsChart'), {{
      type: 'bar',
      data: {{ labels: metricLabels, datasets: [{{
        label: '%', data: metricData,
        backgroundColor: metricData.map(v => v >= 80 ? 'rgba(52,211,153,.75)' : v >= 50 ? 'rgba(96,165,250,.75)' : 'rgba(248,113,113,.75)'),
      }}]}},
      options: {{ indexAxis: 'y', scales: {{ x: {{ max: 100, ticks: {{ callback: v => v + '%' }} }} }},
        plugins: {{ legend: {{ display: false }} }} }}
    }});
    new Chart(document.getElementById('kindChart'), {{
      type: 'bar',
      data: {{
        labels: {json.dumps(kind_labels, ensure_ascii=False)},
        datasets: [
          {{ label: 'Pass %', data: {json.dumps(kind_pass)}, backgroundColor: 'rgba(96,165,250,.8)' }},
          {{ label: 'N cases', data: {json.dumps(kind_n)}, backgroundColor: 'rgba(148,163,184,.35)', yAxisID: 'y1' }},
        ]
      }},
      options: {{
        scales: {{
          y: {{ max: 100, ticks: {{ callback: v => v + '%' }} }},
          y1: {{ position: 'right', grid: {{ drawOnChartArea: false }} }}
        }}
      }}
    }});
    new Chart(document.getElementById('modeChart'), {{
      type: 'doughnut',
      data: {{
        labels: {json.dumps(mode_labels, ensure_ascii=False)},
        datasets: [{{ data: {json.dumps(mode_counts)}, backgroundColor: [
          '#60a5fa','#34d399','#a78bfa','#fbbf24','#f87171','#94a3b8','#fb923c'
        ]}}]
      }},
      options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
    }});
  </script>
</body>
</html>"""


def _icon(val) -> str:
    if val is True:
        return '✓'
    if val is False:
        return '✗'
    return '—'


def _esc(text: str) -> str:
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='RAG benchmark HTML dashboard')
    parser.add_argument('--gold', type=Path, default=DEFAULT_GOLD)
    parser.add_argument('--input', type=Path, default=DEFAULT_OUT.with_suffix('.json'))
    parser.add_argument('--html', type=Path, default=DEFAULT_HTML)
    parser.add_argument('--no-run', action='store_true', help='Skip benchmark; only render from --input')
    parser.add_argument('--open', action='store_true', help='Open dashboard in default browser')
    args = parser.parse_args(argv)

    if not args.no_run:
        missing = missing_corpus_paths(json.loads(args.gold.read_text(encoding='utf-8')))
        if missing:
            raise SystemExit(
                'Missing eval PDFs: run .\\scripts\\sync-eval-corpus.ps1 from repo root.'
            )
        report = run_benchmark(args.gold)
        args.input.parent.mkdir(parents=True, exist_ok=True)
        args.input.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        DEFAULT_OUT.write_text(
            __import__('eval.rag_benchmark', fromlist=['render_markdown']).render_markdown(report),
            encoding='utf-8',
        )
    elif not args.input.is_file():
        raise SystemExit(f'No report JSON at {args.input}; run without --no-run first.')

    if args.no_run:
        report = json.loads(args.input.read_text(encoding='utf-8'))

    gold_meta = _load_gold_cases()
    html = render_html(report, gold_meta)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(html, encoding='utf-8')
    print(f'Dashboard: {args.html.resolve()}')
    if args.open:
        webbrowser.open(args.html.resolve().as_uri())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())