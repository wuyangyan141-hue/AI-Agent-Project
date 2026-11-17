"""LangGraph nodes for study flows with human-in-the-loop."""
from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from ..agent.intent import StudyIntent
from ..database import store
from ..skills.review_session import daily_quiz, public_review, save_quiz_items
from .parse import (
    parse_plan_utterance,
    parse_quiz_utterance,
    plan_missing_fields,
    plan_needs_hitl,
    quiz_missing_fields,
    quiz_needs_hitl,
)
from .schemas import PLAN_HITL_SCHEMA, QUIZ_HITL_SCHEMA
from .state import CompanionState


def quiz_collect(state: CompanionState) -> CompanionState:
    parsed = parse_quiz_utterance(state.get('user_text') or '')
    params: dict[str, Any] = {**(state.get('quiz_params') or {}), **parsed}
    if quiz_needs_hitl(params):
        resume = interrupt({
            **QUIZ_HITL_SCHEMA,
            'missing': quiz_missing_fields(params),
            'defaults': {
                'limit': str(params.get('limit', 3)),
                'difficulty': params.get('difficulty', 'standard'),
            },
        })
        if isinstance(resume, dict):
            merged = dict(resume)
            if merged.get('limit') not in (None, ''):
                merged['limit'] = int(merged['limit'])
            params.update(merged)
        params['confirmed'] = True
    else:
        params['confirmed'] = True
    return {**state, 'quiz_params': params}


def quiz_run(state: CompanionState) -> CompanionState:
    params = state.get('quiz_params') or {}
    session_id = state.get('session_id')
    doc_ids = state.get('document_ids')
    quiz = daily_quiz(
        document_ids=doc_ids,
        limit=int(params.get('limit') or 3),
        difficulty=str(params.get('difficulty') or 'standard'),
    )
    with store.connect() as db:
        created = save_quiz_items(db, quiz['items'], session_id)
    first = public_review(created[0]) if created else {}
    return {
        **state,
        'status': 'done',
        'result': {
            'type': 'quiz',
            'quiz': quiz,
            'created': [public_review(q) for q in created],
            'first': first,
        },
    }


def plan_collect(state: CompanionState) -> CompanionState:
    intent = StudyIntent.model_validate(state.get('intent') or {})
    parsed = parse_plan_utterance(state.get('user_text') or '')
    params: dict[str, Any] = {
        'goal': (intent.goal or '').strip(),
        'days': intent.days or parsed.get('days'),
        'minutes_per_day': intent.minutes_per_day or parsed.get('minutes_per_day'),
        **(state.get('plan_params') or {}),
    }
    if plan_needs_hitl(params, require_goal=intent.action == 'plan'):
        resume = interrupt({
            **PLAN_HITL_SCHEMA,
            'missing': plan_missing_fields(params, require_goal=intent.action == 'plan'),
            'defaults': {
                'goal': params.get('goal', ''),
                'days': str(params.get('days') or 3),
                'minutes_per_day': str(params.get('minutes_per_day') or 45),
            },
        })
        if isinstance(resume, dict):
            merged = dict(resume)
            if merged.get('days') not in (None, ''):
                merged['days'] = int(merged['days'])
            if merged.get('minutes_per_day') not in (None, ''):
                merged['minutes_per_day'] = int(merged['minutes_per_day'])
            params.update(merged)
        params['confirmed'] = True
    else:
        params['confirmed'] = True
    return {**state, 'plan_params': params}


def plan_run(state: CompanionState) -> CompanionState:
    params = state.get('plan_params') or {}
    intent = StudyIntent.model_validate(state.get('intent') or {})
    merged = intent.model_copy(
        update={
            'goal': (params.get('goal') or intent.goal or '').strip(),
            'days': int(params.get('days') or intent.days or 3),
            'minutes_per_day': int(params.get('minutes_per_day') or intent.minutes_per_day or 45),
        }
    )
    return {
        **state,
        'status': 'done',
        'result': {'type': 'plan_ready', 'intent': merged.model_dump(), 'kind': intent.action},
    }