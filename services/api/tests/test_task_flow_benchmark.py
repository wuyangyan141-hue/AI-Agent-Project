from pathlib import Path

import pytest

from eval.task_flow_benchmark import DEFAULT_GOLD, run_benchmark


def test_task_flow_routing_gold_exists():
    assert DEFAULT_GOLD.is_file()
    data = __import__('json').loads(DEFAULT_GOLD.read_text(encoding='utf-8'))
    assert data['name'] == 'task_flow_routing_v1'
    assert len(data['cases']) >= 35
    layers = {c['layer'] for c in data['cases']}
    assert layers == {'intent', 'route', 'turn'}


def test_task_flow_benchmark_pass_rate():
    report = run_benchmark()
    m = report['metrics']
    assert m['n'] >= 35
    assert m['pass_rate'] >= 0.95
    assert m['intent_pass_rate'] >= 0.95
    assert m['turn_pass_rate'] >= 0.9