"""Turn dispatcher: command > skip > review answer > knowledge > chat."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..knowledge.routing import CONFUSED, QUESTION, SOCIAL, route_request
from .entities import (
    is_give_up_review,
    is_objective_review_answer,
    is_skip_review,
    normalize_utterance,
)
from .intent import StudyIntent, explicit_intent

COMMAND_ACTIONS = frozenset({'plan', 'replan', 'focus', 'done', 'review', 'quiz', 'weak', 'next', 'today'})
# Soft coach intents must not swallow a waiting review answer (e.g. 「不知道」→ next).
SOFT_WHILE_WAITING = frozenset({'next'})
TurnKind = Literal['skip', 'command', 'review_answer', 'knowledge', 'chat', 'plan_followup']


@dataclass(frozen=True)
class TurnDecision:
    kind: TurnKind
    intent: StudyIntent
    route: str
    text: str
    normalized: str


def resolve_turn(
    text: str,
    *,
    intent: StudyIntent,
    route: str,
    waiting: bool,
    personal: bool = False,
    pending_plan: bool = False,
    force_review_answer: bool = False,
    general: bool = False,
) -> TurnDecision:
    """Apply a single priority order for pet / websocket turns.

    Priority:
      1. skip waiting review
      2. explicit study commands (never graded as answers)
      3. pending plan goal follow-up
      4. waiting review answer (beats forced knowledge for option letters)
      5. knowledge / summary / compare / personal
      6. ordinary chat
    """
    normalized = normalize_utterance(text)
    base = TurnDecision(kind='chat', intent=intent, route=route, text=text, normalized=normalized)

    if waiting and is_skip_review(normalized):
        return TurnDecision('skip', intent, route, text, normalized)

    if waiting and (
        force_review_answer
        or is_give_up_review(normalized)
        or is_objective_review_answer(normalized)
    ):
        return TurnDecision('review_answer', intent, route, text, normalized)

    # 「看不懂」etc. always need an explanation, never another plan draft.
    if CONFUSED.search(normalized) and not general:
        return TurnDecision('knowledge', intent.model_copy(update={'action': 'chat'}), 'knowledge', text, normalized)

    if intent.action in COMMAND_ACTIONS and not (waiting and intent.action in SOFT_WHILE_WAITING):
        return TurnDecision('command', intent, route, text, normalized)

    if pending_plan and route == 'chat' and not SOCIAL.search(normalized) and not QUESTION.search(normalized) and not CONFUSED.search(normalized):
        # Caller should already have filled intent.goal; keep kind for clarity.
        if intent.action == 'plan' and intent.goal.strip():
            return TurnDecision('plan_followup', intent, route, text, normalized)

    if waiting and intent.action in SOFT_WHILE_WAITING:
        return TurnDecision('review_answer', intent, route, text, normalized)

    if waiting and intent.action == 'chat' and not personal and not general and not SOCIAL.search(normalized):
        # Selected-doc scope sets knowledge=true and used to steal answers like「B」.
        # Only divert to RAG when the user clearly asks a material question.
        clearly_asking = route in {'summary', 'compare'} or (
            QUESTION.search(normalized) and len(normalized) > 4
        )
        if not clearly_asking:
            return TurnDecision('review_answer', intent, route, text, normalized)

    if personal or route in {'knowledge', 'summary', 'compare'}:
        return TurnDecision('knowledge', intent, route, text, normalized)

    return base


def classify_route(
    text: str,
    *,
    forced: bool = False,
    general: bool = False,
    has_documents: bool = False,
    active_topic: bool = False,
) -> str:
    return route_request(
        normalize_utterance(text),
        forced=forced,
        general=general,
        has_documents=has_documents,
        active_topic=active_topic,
    )


def classify_explicit(text: str) -> StudyIntent:
    return explicit_intent(normalize_utterance(text))
