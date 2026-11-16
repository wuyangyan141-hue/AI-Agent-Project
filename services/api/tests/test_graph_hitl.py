"""LangGraph HITL smoke tests."""
from __future__ import annotations

from app.graph.parse import plan_missing_fields, plan_needs_hitl, quiz_missing_fields, quiz_needs_hitl
from app.graph.plan_revise import plan_revise_hitl
from app.graph.runner import resume_quiz_flow, run_quiz_flow


def test_quiz_needs_hitl_without_explicit_params():
    assert quiz_needs_hitl({}) is True
    assert quiz_needs_hitl({'limit': 3}) is True
    assert quiz_needs_hitl({'limit': 3, 'difficulty': 'standard'}) is False
    assert quiz_needs_hitl({'limit': 3, 'difficulty': 'standard', 'daily': True}) is False


def test_plan_needs_hitl_missing_schedule():
    assert plan_needs_hitl({'goal': '复习数据库'}, require_goal=True) is True
    assert plan_needs_hitl({'goal': '复习数据库', 'days': 3, 'minutes_per_day': 30}, require_goal=True) is False


def test_run_quiz_flow_daily_skips_hitl(monkeypatch):
    monkeypatch.setattr(
        'app.graph.nodes.daily_quiz',
        lambda **kwargs: {
            'kind': 'daily_quiz',
            'count': 1,
            'items': [{'topic': '测试', 'question': '【单选题】示例', 'question_type': 'multiple_choice', 'options': [], 'correct_key': 'A'}],
            'difficulty': 'standard',
            'instruction': '',
        },
    )
    out = run_quiz_flow(session_id='test-session-daily', user_text='今日小测', document_ids=None)
    assert out.get('status') == 'done'
    assert out.get('first')


def test_run_quiz_flow_interrupts_without_params():
    out = run_quiz_flow(session_id='test-session-hitl', user_text='我想小测', document_ids=None)
    assert out.get('status') == 'hitl'
    assert out.get('kind') == 'quiz_params'
    assert out.get('hitl', {}).get('fields')


def test_missing_field_hints():
    assert quiz_missing_fields({}) == ['limit', 'difficulty']
    assert plan_missing_fields({'goal': '数据库'}, require_goal=True) == ['days', 'minutes_per_day']


def test_plan_revise_hitl_includes_preview():
    hitl = plan_revise_hitl(
        {'id': 1, 'goal': '复习索引', 'steps': [{'day': 1, 'title': '阅读', 'minutes': 30}]},
        'plan',
    )
    assert hitl['kind'] == 'plan_revise'
    assert '阅读' in (hitl.get('preview') or '')
    assert hitl['defaults']['draft_id'] == 1


def test_resume_quiz_flow_generates_questions():
    thread = 'test-session-hitl-resume'
    first = run_quiz_flow(session_id=thread, user_text='我想小测', document_ids=None)
    assert first.get('status') == 'hitl'
    resumed = resume_quiz_flow(thread, {'limit': 2, 'difficulty': 'easy'})
    assert resumed.get('status') == 'done'
    created = resumed.get('created') or []
    assert len(created) >= 1