"""Benchmark explicit intent, knowledge routing, and turn dispatch (no API / no LLM).

Usage (from services/api):
  python -m eval.task_flow_benchmark
  # Dev-only; eval/out task-flow artifacts are gitignored. See eval.langsmith_detect_intent for LLM reports.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .corpus_loader import EVAL_DIR

DEFAULT_GOLD = EVAL_DIR / 'gold' / 'task_flow_routing.json'
DEFAULT_OUT = EVAL_DIR / 'out' / 'task-flow-results.md'
DEFAULT_HTML = EVAL_DIR / 'out' / 'task-flow-dashboard.html'


@dataclass
class CaseResult:
    id: str
    layer: str
    text: str
    passed: bool
    expected: dict
    actual: dict
    notes: str = ''


def _load_gold(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _build_intent(case: dict, context: dict):
    from app.agent.intent import StudyIntent, explicit_intent

    if context.get('intent_action'):
        fields = {
            'action': context.get('intent_action', 'chat'),
            'goal': context.get('intent_goal', ''),
            'days': context.get('days', 3),
            'minutes_per_day': context.get('minutes_per_day', 45),
            'topic': context.get('topic', ''),
        }
        return StudyIntent(**fields)
    return explicit_intent(case['text'])


def _run_intent(case: dict) -> dict:
    from app.agent.dispatch import classify_explicit

    intent = classify_explicit(case['text'])
    return {
        'action': intent.action,
        'goal': intent.goal,
        'days': intent.days,
        'minutes_per_day': intent.minutes_per_day,
        'minutes': intent.minutes,
        'seconds': intent.seconds,
        'topic': intent.topic,
    }


def _run_route(case: dict) -> dict:
    from app.agent.dispatch import classify_route

    ctx = case.get('context') or {}
    route = classify_route(
        case['text'],
        forced=bool(ctx.get('forced')),
        general=bool(ctx.get('general')),
        has_documents=bool(ctx.get('has_documents')),
        active_topic=bool(ctx.get('active_topic')),
    )
    return {'route': route}


def _run_turn(case: dict) -> dict:
    from app.agent.dispatch import resolve_turn

    ctx = case.get('context') or {}
    intent = _build_intent(case, ctx)
    route = ctx.get('route', 'chat')
    decision = resolve_turn(
        case['text'],
        intent=intent,
        route=route,
        waiting=bool(ctx.get('waiting')),
        personal=bool(ctx.get('personal')),
        pending_plan=bool(ctx.get('pending_plan')),
        force_review_answer=bool(ctx.get('force_review_answer')),
        general=bool(ctx.get('general')),
    )
    return {
        'kind': decision.kind,
        'action': decision.intent.action,
        'route': decision.route,
        'goal': decision.intent.goal,
        'topic': decision.intent.topic,
    }


def _match(expect: dict, actual: dict) -> tuple[bool, str]:
    mismatches = []
    for key, want in expect.items():
        if key not in actual:
            mismatches.append(f'missing actual[{key}]')
            continue
        got = actual[key]
        if isinstance(want, str):
            if str(got).casefold() != str(want).casefold():
                mismatches.append(f'{key}: want {want!r}, got {got!r}')
        elif got != want:
            mismatches.append(f'{key}: want {want!r}, got {got!r}')
    return (not mismatches, '; '.join(mismatches))


def evaluate_case(case: dict) -> CaseResult:
    layer = case['layer']
    expect = case.get('expect') or {}
    if layer == 'intent':
        actual = _run_intent(case)
    elif layer == 'route':
        actual = _run_route(case)
    elif layer == 'turn':
        actual = _run_turn(case)
    else:
        raise ValueError(f'unknown layer {layer!r}')
    ok, notes = _match(expect, actual)
    # Only include expected keys in actual snapshot for reporting clarity.
    slim = {k: actual.get(k) for k in expect}
    slim.update({k: actual[k] for k in ('action', 'route', 'kind') if k in actual and k not in slim})
    return CaseResult(
        id=case['id'],
        layer=layer,
        text=case['text'],
        passed=ok,
        expected=expect,
        actual=slim,
        notes=notes,
    )


def summarize(results: list[CaseResult]) -> dict:
    def rate(rows: list[CaseResult]) -> float:
        return round(sum(1 for r in rows if r.passed) / len(rows), 4) if rows else 0.0

    by_layer: dict[str, list[CaseResult]] = {}
    for r in results:
        by_layer.setdefault(r.layer, []).append(r)
    return {
        'n': len(results),
        'pass_rate': rate(results),
        'intent_pass_rate': rate(by_layer.get('intent', [])),
        'route_pass_rate': rate(by_layer.get('route', [])),
        'turn_pass_rate': rate(by_layer.get('turn', [])),
        'intent_n': len(by_layer.get('intent', [])),
        'route_n': len(by_layer.get('route', [])),
        'turn_n': len(by_layer.get('turn', [])),
    }


def render_markdown(report: dict) -> str:
    m = report['metrics']
    lines = [
        '# Task-flow routing benchmark',
        '',
        f"- Suite: `{report.get('name')}`",
        f"- Generated (UTC): {report.get('generated_at')}",
        '- Scope: `explicit_intent` · `route_request` · `resolve_turn` (deterministic, no LLM)',
        '',
        '## Metrics',
        '',
        '| Metric | Value |',
        '| --- | ---: |',
        f"| Cases | {m['n']} |",
        f"| Overall pass rate | {m['pass_rate']:.0%} |",
        f"| Intent (`explicit_intent`) | {m['intent_pass_rate']:.0%} ({m['intent_n']}) |",
        f"| Route (`route_request`) | {m['route_pass_rate']:.0%} ({m['route_n']}) |",
        f"| Turn (`resolve_turn`) | {m['turn_pass_rate']:.0%} ({m['turn_n']}) |",
        '',
        '## Per-case',
        '',
        '| ID | Layer | Pass | Expected | Actual | Notes |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for row in report['cases']:
        lines.append(
            f"| {row['id']} | {row['layer']} | {'Y' if row['passed'] else 'N'} | "
            f"`{json.dumps(row['expected'], ensure_ascii=False)}` | "
            f"`{json.dumps(row['actual'], ensure_ascii=False)}` | {row.get('notes') or ''} |"
        )
    fails = [r for r in report['cases'] if not r['passed']]
    lines += ['', '## Failures', '']
    if not fails:
        lines.append('All cases passed.')
    else:
        for row in fails:
            lines.append(f"- `{row['id']}` ({row['layer']}): {row.get('notes')}")
    lines += [
        '',
        '## Reproduce',
        '',
        '```bash',
        'cd services/api',
        '.venv/Scripts/python.exe -m eval.task_flow_benchmark --html',
        '```',
        '',
    ]
    return '\n'.join(lines)


def render_html(report: dict) -> str:
    m = report['metrics']
    cases = report['cases']
    fail_rows = [c for c in cases if not c['passed']]
    layer_labels = ['intent', 'route', 'turn']
    layer_rates = [m.get(f'{x}_pass_rate', 0) * 100 for x in layer_labels]
    layer_ns = [m.get(f'{x}_n', 0) for x in layer_labels]

    rows = []
    for c in cases:
        status = 'pass' if c['passed'] else 'fail'
        rows.append(
            f'<tr class="{status}"><td><code>{c["id"]}</code></td><td>{c["layer"]}</td>'
            f'<td>{"PASS" if c["passed"] else "FAIL"}</td>'
            f'<td><code>{_esc(json.dumps(c["expected"], ensure_ascii=False))}</code></td>'
            f'<td><code>{_esc(json.dumps(c["actual"], ensure_ascii=False))}</code></td>'
            f'<td>{_esc(c.get("text", "")[:80])}</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-Hans"><head><meta charset="utf-8"/>
<title>Task-flow benchmark</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#0f1419;color:#e7ecf3;padding:1.5rem 2rem}}
.card{{background:#1a2332;border:1px solid #2d3a4f;border-radius:12px;padding:1rem;margin:1rem 0}}
.val{{font-size:2rem;color:#60a5fa}} table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th,td{{border-bottom:1px solid #2d3a4f;padding:.4rem;text-align:left}}
tr.fail{{background:rgba(248,113,113,.1)}}
</style></head><body>
<h1>Task-flow routing</h1>
<p>Suite {report.get('name')} · {m['n']} cases · pass {m['pass_rate']:.0%} · failures {len(fail_rows)}</p>
<div class="card"><div class="val">{m['pass_rate']:.0%}</div> overall</div>
<div class="card" style="max-width:520px"><canvas id="layerChart"></canvas></div>
<div class="card table-wrap"><table><thead><tr><th>ID</th><th>Layer</th><th>Pass</th><th>Expected</th><th>Actual</th><th>Text</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<script>
new Chart(document.getElementById('layerChart'),{{
  type:'bar',
  data:{{labels:{json.dumps(layer_labels)},datasets:[{{label:'Pass %',data:{json.dumps(layer_rates)}}}] }},
  options:{{scales:{{y:{{max:100,ticks:{{callback:v=>v+'%'}}}}}}}}
}});
</script></body></html>"""


def _esc(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def run_benchmark(gold_path: Path | None = None) -> dict:
    root = EVAL_DIR.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    gold = _load_gold(gold_path or DEFAULT_GOLD)
    results = [evaluate_case(c) for c in gold['cases']]
    metrics = summarize(results)
    return {
        'name': gold.get('name'),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'metrics': metrics,
        'cases': [asdict(r) for r in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Task-flow routing benchmark')
    parser.add_argument('--gold', type=Path, default=DEFAULT_GOLD)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--html', type=Path, default=None, nargs='?', const=DEFAULT_HTML)
    args = parser.parse_args(argv)

    report = run_benchmark(args.gold)
    md = render_markdown(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding='utf-8')
    json_path = args.out.with_suffix('.json')
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(md)
    if args.html:
        args.html.write_text(render_html(report), encoding='utf-8')
        print(f'HTML: {args.html.resolve()}')
    print(f'Wrote {args.out}')
    return 0 if report['metrics']['pass_rate'] >= 0.95 else 1


if __name__ == '__main__':
    raise SystemExit(main())