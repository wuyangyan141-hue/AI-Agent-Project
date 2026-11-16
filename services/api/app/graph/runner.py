"""Invoke study LangGraph flows and normalize HITL interrupts."""
from __future__ import annotations

from typing import Any

from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from ..agent.intent import StudyIntent
from .build import plan_graph, quiz_graph
from .state import CompanionState


def _thread_id(session_id: str | None) -> str:
    return session_id or 'default-thread'


def _config(thread_id: str) -> dict:
    return {'configurable': {'thread_id': thread_id}}


def _hitl_from_state(final: dict[str, Any]) -> dict[str, Any] | None:
    raw = final.get('__interrupt__') if isinstance(final, dict) else None
    if not raw:
        return None
    first = raw[0]
    value = getattr(first, 'value', first)
    return value if isinstance(value, dict) else None


def _unwrap_interrupt(exc: GraphInterrupt) -> dict[str, Any] | None:
    interrupts = getattr(exc, 'interrupts', None) or []
    if interrupts:
        first = interrupts[0]
        value = getattr(first, 'value', first)
        if isinstance(value, dict):
            return value
    return None


def _normalize_final(final: dict[str, Any]) -> dict[str, Any]:
    hitl = _hitl_from_state(final)
    if hitl:
        return {'status': 'hitl', 'kind': hitl.get('kind'), 'hitl': hitl, 'interrupt_id': final.get('thread_id')}
    if final.get('status') == 'done':
        return {'status': 'done', **(final.get('result') or {})}
    return {'status': 'error', 'error': final.get('error') or 'graph failed'}


def run_quiz_flow(
    *,
    session_id: str | None,
    user_text: str,
    document_ids: list[str] | None,
) -> dict[str, Any]:
    thread = _thread_id(session_id)
    graph = quiz_graph()
    initial: CompanionState = {
        'thread_id': thread,
        'session_id': session_id,
        'user_text': user_text,
        'action': 'quiz',
        'document_ids': document_ids,
    }
    try:
        final = graph.invoke(initial, config=_config(thread))
    except GraphInterrupt as exc:
        hitl = _unwrap_interrupt(exc)
        return {'status': 'hitl', 'kind': 'quiz_params', 'hitl': hitl, 'interrupt_id': thread}
    return _normalize_final(final)


def resume_quiz_flow(thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    graph = quiz_graph()
    try:
        final = graph.invoke(Command(resume=payload), config=_config(thread_id))
    except GraphInterrupt as exc:
        hitl = _unwrap_interrupt(exc)
        return {'status': 'hitl', 'kind': 'quiz_params', 'hitl': hitl, 'interrupt_id': thread_id}
    return _normalize_final(final)


def run_plan_flow(
    *,
    session_id: str | None,
    user_text: str,
    intent: StudyIntent,
    document_ids: list[str] | None,
) -> dict[str, Any]:
    thread = _thread_id(session_id)
    graph = plan_graph()
    initial: CompanionState = {
        'thread_id': thread,
        'session_id': session_id,
        'user_text': user_text,
        'action': intent.action,
        'document_ids': document_ids,
        'intent': intent.model_dump(),
    }
    try:
        final = graph.invoke(initial, config=_config(thread))
    except GraphInterrupt as exc:
        hitl = _unwrap_interrupt(exc)
        return {'status': 'hitl', 'kind': 'plan_params', 'hitl': hitl, 'interrupt_id': thread}
    return _normalize_final(final)


def resume_plan_flow(thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    graph = plan_graph()
    try:
        final = graph.invoke(Command(resume=payload), config=_config(thread_id))
    except GraphInterrupt as exc:
        hitl = _unwrap_interrupt(exc)
        return {'status': 'hitl', 'kind': 'plan_params', 'hitl': hitl, 'interrupt_id': thread_id}
    return _normalize_final(final)