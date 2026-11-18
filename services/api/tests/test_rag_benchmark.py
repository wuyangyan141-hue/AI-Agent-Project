from eval.rag_benchmark import run_benchmark, summarize, CaseResult


def test_rag_small_sample_core_metrics(tmp_path):
    report = run_benchmark(data_dir=tmp_path / 'bench')
    metrics = report['metrics']
    assert metrics['n'] == 12
    # Core offline claims for the report table.
    assert metrics['in_scope_pass_rate'] >= 0.8
    assert metrics['refusal_accuracy'] >= 0.75
    assert metrics['pass_rate'] >= 0.75
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
