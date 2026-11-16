"""Parse optional study parameters from natural language."""
from __future__ import annotations

import re


def parse_quiz_utterance(text: str) -> dict:
    out: dict = {}
    m = re.search(r'(\d+)\s*道', text)
    if m:
        out['limit'] = max(1, min(5, int(m.group(1))))
    if re.search(r'困难|高难度|hard', text, re.I):
        out['difficulty'] = 'hard'
    elif re.search(r'简单|轻松|容易|easy', text, re.I):
        out['difficulty'] = 'easy'
    elif re.search(r'标准|中等|normal', text, re.I):
        out['difficulty'] = 'standard'
    return out


def parse_plan_utterance(text: str) -> dict:
    out: dict = {}
    m = re.search(r'(\d+)\s*天', text)
    if m:
        out['days'] = max(1, min(14, int(m.group(1))))
    m2 = re.search(r'每天\s*(\d+)\s*分钟|(\d+)\s*分钟/天', text)
    if m2:
        out['minutes_per_day'] = max(15, min(240, int(m2.group(1) or m2.group(2))))
    return out


def quiz_needs_hitl(params: dict) -> bool:
    if params.get('confirmed'):
        return False
    return 'limit' not in params or 'difficulty' not in params


def plan_needs_hitl(params: dict, *, require_goal: bool) -> bool:
    if params.get('confirmed'):
        return False
    if require_goal and not (params.get('goal') or '').strip():
        return True
    return 'days' not in params or 'minutes_per_day' not in params