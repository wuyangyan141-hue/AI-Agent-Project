"""LangGraph companion state."""
from __future__ import annotations

from typing import Any, Literal, TypedDict

StudyAction = Literal['quiz', 'plan', 'replan', 'none']


class QuizParams(TypedDict, total=False):
    limit: int
    difficulty: Literal['easy', 'standard', 'hard']
    question_types: list[str]
    confirmed: bool


class PlanParams(TypedDict, total=False):
    goal: str
    days: int
    minutes_per_day: int
    confirmed: bool


class CompanionState(TypedDict, total=False):
    thread_id: str
    session_id: str | None
    user_text: str
    action: StudyAction
    document_ids: list[str] | None
    intent: dict[str, Any]
    quiz_params: QuizParams
    plan_params: PlanParams
    status: Literal['hitl', 'done', 'legacy', 'error']
    hitl: dict[str, Any] | None
    result: dict[str, Any] | None
    error: str | None