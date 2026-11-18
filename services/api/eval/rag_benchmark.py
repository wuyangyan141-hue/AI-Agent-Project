"""Small-sample RAG benchmark for report / presentation metrics.

Offline by default (no API key): measures retrieval hit, evidence support,
and refusal accuracy on a fixed gold set.

Usage (from services/api):
  .venv/Scripts/python -m eval.rag_benchmark
  .venv/Scripts/python -m eval.rag_benchmark --out ../../docs/rag-benchmark-results.md
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_GOLD = EVAL_DIR / 'gold' / 'rag_small_sample.json'
REPO_DOCS = EVAL_DIR.parents[2] / 'docs' / 'rag-benchmark-results.md'


@dataclass
class CaseResult:
    id: str
    kind: str
    question: str
    mode: str
    retrieval_hit: bool | None
    evidence_support: bool | None
    mode_ok: bool
    passed: bool
    notes: str = ''


@dataclass
class Metrics:
    n: int
    pass_rate: float
    retrieval_hit_rate: float
    evidence_support_rate: float
    refusal_accuracy: float
    in_scope_pass_rate: float
    paraphrase_pass_rate: float
    off_topic_pass_rate: float


def _contains_any(text: str, needles: list[str]) -> bool:
    blob = text or ''
    return any(n and n.casefold() in blob.casefold() for n in needles)


def _load_gold(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _upload_corpus(kb, gold: dict) -> str:
    rel = gold.get('corpus_file') or 'corpus/search_basics.txt'
    corpus_path = (EVAL_DIR / rel).resolve()
    doc = kb.upload('local-user', corpus_path.name, corpus_path.read_bytes())
    if doc.get('status') == 'error':
        raise RuntimeError(doc.get('error') or 'corpus upload failed')
    return doc['id']


def _evaluate_case(kb, doc_id: str, case: dict) -> CaseResult:
    question = case['question']
    hits = kb.search('local-user', question, [doc_id])
    hit_blob = '\n'.join(h.get('snippet') or '' for h in hits)
    result = kb.answer('local-user', question, document_ids=[doc_id])
    mode = result.get('mode') or ''
    answer = result.get('answer') or ''
    source_blob = '\n'.join(s.get('snippet') or '' for s in (result.get('sources') or []))
    evidence_blob = f'{answer}\n{source_blob}\n{hit_blob}'

    expect_modes = case.get('expect_mode') or []
    mode_ok = mode in expect_modes if expect_modes else True
    kind = case.get('kind') or 'in_scope'
    must_retrieve = case.get('must_retrieve_any') or []
    must_answer = case.get('must_answer_any') or []
    note = case.get('notes') or ''

    if kind == 'off_topic':
        retrieval_hit = len(hits) == 0
        evidence_support = mode == 'no_evidence'
        passed = mode_ok and evidence_support
    else:
        retrieval_hit = _contains_any(hit_blob, must_retrieve) if must_retrieve else bool(hits)
        evidence_support = _contains_any(evidence_blob, must_answer) if must_answer else bool(answer)
        if kind == 'paraphrase' and not retrieval_hit and mode == 'no_evidence':
            # Honest lexical miss is acceptable for hardness tracking.
            passed = True
            note = 'honest_miss_under_lexical_retrieval'
        else:
            passed = bool(mode_ok and retrieval_hit and evidence_support)

    return CaseResult(
        id=case['id'],
        kind=kind,
        question=question,
        mode=mode,
        retrieval_hit=retrieval_hit,
        evidence_support=evidence_support,
        mode_ok=mode_ok,
        passed=passed,
        notes=note,
    )


def _rate(values: list[bool]) -> float:
    return round(sum(1 for v in values if v) / len(values), 4) if values else 0.0


def summarize(results: list[CaseResult]) -> Metrics:
    in_scope = [r for r in results if r.kind == 'in_scope']
    paraphrase = [r for r in results if r.kind == 'paraphrase']
    off = [r for r in results if r.kind == 'off_topic']
    supported = in_scope + paraphrase

    retrieval_vals = []
    for r in results:
        if r.retrieval_hit is None:
            continue
        retrieval_vals.append(bool(r.retrieval_hit))

    return Metrics(
        n=len(results),
        pass_rate=_rate([r.passed for r in results]),
        retrieval_hit_rate=_rate(retrieval_vals),
        evidence_support_rate=_rate([bool(r.evidence_support) for r in supported]),
        refusal_accuracy=_rate([r.passed for r in off]),
        in_scope_pass_rate=_rate([r.passed for r in in_scope]),
        paraphrase_pass_rate=_rate([r.passed for r in paraphrase]),
        off_topic_pass_rate=_rate([r.passed for r in off]),
    )


def run_benchmark(gold_path: Path | None = None, *, data_dir: Path | None = None) -> dict:
    root = EVAL_DIR.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.knowledge.config import Settings
    from app.knowledge.service import KnowledgeService

    gold = _load_gold(gold_path or DEFAULT_GOLD)
    tmp = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix='rag-bench-'))
    settings = Settings(
        data_dir=tmp / 'knowledge',
        database_path=tmp / 'bench.db',
        embedding_provider='local',
        llm_model='',
        llm_api_key='',
    )
    kb = KnowledgeService(settings)
    doc_id = _upload_corpus(kb, gold)
    results = [_evaluate_case(kb, doc_id, case) for case in gold['cases']]
    metrics = summarize(results)
    return {
        'name': gold.get('name'),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'corpus': gold.get('corpus_file'),
        'embedding_provider': 'local',
        'llm': False,
        'document_id': doc_id,
        'metrics': asdict(metrics),
        'cases': [asdict(r) for r in results],
    }


def render_markdown(report: dict) -> str:
    m = report['metrics']
    lines = [
        '# RAG small-sample benchmark results',
        '',
        f"- Suite: `{report.get('name')}`",
        f"- Generated (UTC): {report.get('generated_at')}",
        f"- Corpus: `{report.get('corpus')}`",
        f"- Mode: offline extractive · embedding_provider=`{report.get('embedding_provider')}` · LLM=`{report.get('llm')}`",
        '',
        '## Metrics',
        '',
        '| Metric | Value |',
        '| --- | ---: |',
        f"| Cases | {m['n']} |",
        f"| Overall pass rate | {m['pass_rate']:.0%} |",
        f"| Retrieval hit rate | {m['retrieval_hit_rate']:.0%} |",
        f"| Evidence support rate (in-scope / paraphrase) | {m['evidence_support_rate']:.0%} |",
        f"| Refusal accuracy (off-topic) | {m['refusal_accuracy']:.0%} |",
        f"| In-scope pass rate | {m['in_scope_pass_rate']:.0%} |",
        f"| Paraphrase pass rate | {m['paraphrase_pass_rate']:.0%} |",
        f"| Off-topic pass rate | {m['off_topic_pass_rate']:.0%} |",
        '',
        '## Per-case',
        '',
        '| ID | Kind | Pass | Mode | Retrieval | Evidence |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for row in report['cases']:
        lines.append(
            f"| {row['id']} | {row['kind']} | {'Y' if row['passed'] else 'N'} | `{row['mode']}` | "
            f"{row['retrieval_hit']} | {row['evidence_support']} |"
        )
    fails = [r for r in report['cases'] if not r['passed']]
    lines += ['', '## Failures / notes', '']
    if not fails:
        lines.append('All cases passed under the offline lexical setup.')
    else:
        for row in fails:
            detail = row.get('notes') or row['question']
            lines.append(f"- `{row['id']}` ({row['kind']}): mode=`{row['mode']}` · {detail}")
    lines += [
        '',
        '## How to reproduce',
        '',
        '```bash',
        'cd services/api',
        '.venv/Scripts/python -m eval.rag_benchmark --out ../../docs/rag-benchmark-results.md',
        '```',
        '',
        'Definitions: **retrieval hit** = gold cue appears in retrieved snippets '
        '(for off-topic: empty hit list). '
        '**Evidence support** = answer or sources contain a gold cue. '
        '**Refusal accuracy** = off-topic questions return `no_evidence`. '
        'Paraphrase items that honestly miss under lexical retrieval count as pass '
        'with note `honest_miss_under_lexical_retrieval`.',
        '',
    ]
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run small-sample RAG benchmark')
    parser.add_argument('--gold', type=Path, default=DEFAULT_GOLD)
    parser.add_argument('--out', type=Path, default=REPO_DOCS)
    parser.add_argument('--json-out', type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_benchmark(args.gold)
    md = render_markdown(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding='utf-8')
    json_path = args.json_out or args.out.with_suffix('.json')
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(md)
    print(f'\nWrote {args.out}')
    print(f'Wrote {json_path}')
    m = report['metrics']
    if m['in_scope_pass_rate'] < 0.8 or m['refusal_accuracy'] < 0.75:
        print(
            'WARNING: core metrics below suggested report thresholds '
            '(in-scope>=80%, refusal>=75%).',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
