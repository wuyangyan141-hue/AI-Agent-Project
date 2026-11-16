"""LangGraph HITL smoke tests."""
from __future__ import annotations

from app.graph.parse import plan_needs_hitl, quiz_needs_hitl
from app.graph.runner import resume_quiz_flow, run_quiz_flow


def test_quiz_needs_hitl_without_explicit_params():
    assert quiz_needs_hitl({}) is True
    assert quiz_needs_hitl({'limit': 3}) is True
    assert quiz_needs_hitl({'limit': 3, 'difficulty': 'standard'}) is False


def test_plan_needs_hitl_missing_schedule():
    assert plan_needs_hitl({'goal': '复习数据库'}, require_goal=True) is True
    assert plan_needs_hitl({'goal': '复习数据库', 'days': 3, 'minutes_per_day': 30}, require_goal=True) is False


def test_run_quiz_flow_interrupts_without_params():
    out = run_quiz_flow(session_id='test-session-hitl', user_text='今日小测', document_ids=None)
    assert out.get('status') == 'hitl'
    assert out.get('kind') == 'quiz_params'
    assert out.get('hitl', {}).get('fields')


def test_resume_quiz_flow_generates_questions():
    thread = 'test-session-hitl-resume'
    first = run_quiz_flow(session_id=thread, user_text='今日小测', document_ids=None)
    assert first.get('status') == 'hitl'
    resumed = resume_quiz_flow(thread, {'limit': 2, 'difficulty': 'easy'})
    assert resumed.get('status') == 'done'
    created = resumed.get('created') or []
    assert len(created) >= 1