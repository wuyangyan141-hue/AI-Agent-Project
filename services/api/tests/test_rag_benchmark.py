import pytest

from eval.corpus_loader import EVAL_DIR, missing_corpus_paths
from eval.rag_benchmark import DEFAULT_GOLD, run_benchmark, summarize, CaseResult

PDF_MARKER = EVAL_DIR / 'corpus/dsai5205/DSAI5205_Chapter3_2026.pdf'


def test_rag_small_sample_core_metrics(tmp_path):
    if not PDF_MARKER.is_file():
        pytest.skip('DSAI5205 eval PDFs missing — run scripts/sync-eval-corpus.ps1')
    assert not missing_corpus_paths(__import__('json').loads(DEFAULT_GOLD.read_text(encoding='utf-8')))
    report = run_benchmark(data_dir=tmp_path / 'bench')
    metrics = report['metrics']
    assert metrics['n'] >= 38
    assert metrics['in_scope_pass_rate'] >= 0.8
    assert metrics['refusal_accuracy'] >= 0.7
    assert metrics['pass_rate'] >= 0.7
    assert metrics['answer_clean_rate'] >= 0.8
    kinds = {c['kind'] for c in report['cases']}
    assert {'in_scope', 'off_topic', 'paraphrase', 'compare', 'multi_hop'} <= kinds
    off = [c for c in report['cases'] if c['kind'] == 'off_topic']
    assert off and all(c['mode'] == 'no_evidence' for c in off if c['passed'])


def test_summarize_rates():
    rows = [
        CaseResult('a', 'in_scope', 'q', 'extractive', True, True, True, True),
        CaseResult('b', 'off_topic', 'q', 'no_evidence', True, True, True, True),
        CaseResult('c', 'off_topic', 'q', 'extractive', False, False, False, False),
    ]
    metrics = summarize(rows)
    assert metrics.n == 3
    assert metrics.refusal_accuracy == 0.5
    assert metrics.in_scope_pass_rate == 1.0
