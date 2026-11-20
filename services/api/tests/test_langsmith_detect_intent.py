import json
from pathlib import Path

from eval.langsmith_detect_intent import (
    DEFAULT_GOLD,
    _match_expect,
    make_examples,
    score_intent_match,
    validate_gold,
)


def test_detect_intent_gold_uses_llm_path():
    gold = json.loads(Path(DEFAULT_GOLD).read_text(encoding="utf-8"))
    validate_gold(gold)
    assert len(gold["cases"]) >= 10


def test_intent_match_evaluator():
    ref = {"expect": {"action": "replan"}, "expect_any": {}}
    good = {"action": "replan", "used_llm": True, "explicit_action": "chat"}
    bad = {"action": "chat", "used_llm": True}
    assert score_intent_match(good, ref)["score"] == 1
    assert score_intent_match(bad, ref)["score"] == 0


def test_normalize_outputs_wrapper():
    from eval.langsmith_detect_intent import _normalize_outputs

    inner = {"action": "quiz", "text": "x"}
    assert _normalize_outputs({"output": inner}) == inner
    assert _normalize_outputs(inner) == inner


def test_expect_any_goal():
    ref = {"expect": {"action": "plan"}, "expect_any": {"goal": ["神经网络"]}}
    ok, _ = _match_expect({"action": "plan", "goal": "复习神经网络章节"}, ref)
    assert ok
    fail, notes = _match_expect({"action": "plan", "goal": "数据库"}, ref)
    assert not fail and "goal" in notes


def test_make_examples():
    gold = json.loads(Path(DEFAULT_GOLD).read_text(encoding="utf-8"))
    ex = make_examples(gold)
    assert ex[0]["inputs"]["case_id"]