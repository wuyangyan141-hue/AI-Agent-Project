from eval.langsmith_task_flow import make_examples, score_routing_match, score_layer
from eval.task_flow_benchmark import DEFAULT_GOLD, evaluate_case


def test_task_flow_examples_shape():
    import json

    gold = json.loads(DEFAULT_GOLD.read_text(encoding="utf-8"))
    examples = make_examples(gold)
    assert len(examples) >= 35
    ex = examples[0]
    assert "case_id" in ex["inputs"]
    assert "expect" in ex["reference_outputs"]


def test_langsmith_evaluator_matches_local_benchmark():
    gold_case = {
        "id": "x",
        "layer": "intent",
        "text": "今日小测",
        "expect": {"action": "quiz"},
    }
    local = evaluate_case(gold_case)
    ref = {"expect": {"action": "quiz"}, "layer": "intent"}
    out = {"layer": "intent", "actual": local.actual, "passed": local.passed}
    assert score_routing_match(out, ref)["score"] == 1
    assert score_layer(out, ref)["score"] == 1