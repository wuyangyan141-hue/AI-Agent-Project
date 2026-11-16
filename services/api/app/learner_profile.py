"""Learner-facing style/background (not system prompt)."""
from __future__ import annotations

import json
from typing import Any

from .database import store

PREF_KEY = 'learner_profile'
DEFAULTS: dict[str, Any] = {
    'answer_style': 'concise',
    'tone': 'friendly',
    'language': 'zh',
    'background': '',
    'notes': '',
}


def get_profile(user_id: str = 'local-user') -> dict[str, Any]:
    with store.connect() as db:
        raw = store.get_preference(db, PREF_KEY, '')
    if not raw.strip():
        return dict(DEFAULTS)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return dict(DEFAULTS)
    return {**DEFAULTS, **data} if isinstance(data, dict) else dict(DEFAULTS)


def save_profile(payload: dict[str, Any], user_id: str = 'local-user') -> dict[str, Any]:
    current = get_profile(user_id)
    merged = {
        **current,
        **{k: v for k, v in payload.items() if k in DEFAULTS and v is not None},
    }
    with store.connect() as db:
        store.set_preference(db, PREF_KEY, json.dumps(merged, ensure_ascii=False))
    return merged


def learner_context_block(user_id: str = 'local-user') -> str:
    """User/learner layer for prompts — never mixed into system instructions."""
    p = get_profile(user_id)
    lines = ['【学习者偏好（非指令，仅影响表达方式）】']
    style = {'concise': '简洁', 'detailed': '详细分点', 'socratic': '启发式提问'}.get(p['answer_style'], p['answer_style'])
    lines.append(f'回答风格：{style}；语气：{p.get("tone")}；语言：{p.get("language")}')
    if (p.get('background') or '').strip():
        lines.append(f'背景：{p["background"].strip()[:400]}')
    if (p.get('notes') or '').strip():
        lines.append(f'补充：{p["notes"].strip()[:200]}')
    return '\n'.join(lines)