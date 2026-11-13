"""A deterministic planning workflow that the Agent can call as a tool."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class StudyStep:
    day: int
    title: str
    minutes: int


class ProposedStep(BaseModel):
    day: int = Field(ge=1, le=14)
    title: str = Field(min_length=1, max_length=200)
    minutes: int = Field(ge=5, le=240)


class PlanProposal(BaseModel):
    """Structured model output; validation against user limits follows parsing."""
    steps: list[ProposedStep] = Field(min_length=1, max_length=42)


# Demo / builtin CS topics that must not leak into plans for unrelated uploads.
FOREIGN_CS = re.compile(
    r'Hash|哈希索引|哈希\s*索引|B\+|B\s*\+|B树|B\s*树|数据库索引|叶子节点|范围查询|'
    r'链表连接|开散列|闭散列|开放寻址|哈希冲突',
    re.I,
)


def material_blob(material_context: dict | None) -> str:
    ctx = material_context or {}
    parts = list(ctx.get('topics') or [])
    for source in ctx.get('sources') or []:
        parts.append(source.get('filename') or '')
        parts.append(source.get('section') or '')
        parts.append(source.get('snippet') or '')
    for name in ctx.get('filenames') or []:
        parts.append(name)
    return '\n'.join(parts)


def goal_matches_materials(goal: str, material_context: dict | None) -> bool:
    """False when the goal is a foreign CS topic but the corpus has no such content."""
    text = (goal or '').strip()
    if not text or not FOREIGN_CS.search(text):
        return True
    blob = material_blob(material_context)
    if not blob.strip():
        return True
    return bool(FOREIGN_CS.search(blob))


def grounded_goal(goal: str, material_context: dict | None) -> str:
    """Rewrite an off-corpus goal to the uploaded material topics/filenames."""
    ctx = material_context or {}
    topics = [t for t in (ctx.get('topics') or []) if str(t).strip()]
    filenames = [f for f in (ctx.get('filenames') or []) if str(f).strip()]
    text = (goal or '').strip()
    if goal_matches_materials(text, ctx):
        if text:
            return text
        if topics:
            return topics[0]
        if filenames:
            return f'复习《{filenames[0]}》'
        return ''
    label = '、'.join(topics[:3]) if topics else (filenames[0] if filenames else '')
    if not label:
        return text
    return f'复习《{filenames[0]}》：{label}' if filenames else f'复习资料重点：{label}'


def validate_plan(proposal: PlanProposal, days: int, minutes_per_day: int, material_context: dict | None = None) -> list[StudyStep]:
    """Reject a plausible-looking plan that cannot fit the requested schedule."""
    if not 1 <= days <= 14 or not 15 <= minutes_per_day <= 240:
        raise ValueError('Invalid time budget')
    totals = {day: 0 for day in range(1, days + 1)}
    titles = set()
    blob = material_blob(material_context)
    require_grounding = bool(blob.strip()) and not FOREIGN_CS.search(blob)
    for step in proposal.steps:
        if step.day not in totals or not step.title.strip():
            raise ValueError('Plan contains an invalid day or empty title')
        if require_grounding and FOREIGN_CS.search(step.title):
            raise ValueError('Plan invents topics that are not in the uploaded materials')
        totals[step.day] += step.minutes
        title = step.title.strip().casefold()
        if title in titles:
            raise ValueError('Plan contains repeated tasks')
        titles.add(title)
    if any(total == 0 or total > minutes_per_day for total in totals.values()):
        raise ValueError('Plan must cover each day without exceeding the daily budget')
    return [StudyStep(day=step.day, title=step.title.strip(), minutes=step.minutes)
            for step in sorted(proposal.steps, key=lambda item: item.day)]


def make_study_plan(goal: str, days: int = 3, minutes_per_day: int = 45, material_context: dict | None = None) -> list[StudyStep]:
    goal = grounded_goal(goal, material_context).strip()
    if not goal or not 1 <= days <= 14 or not 15 <= minutes_per_day <= 240:
        raise ValueError('Invalid study goal or schedule')
    topics = [t for t in ((material_context or {}).get('topics') or []) if str(t).strip()]
    stages = ('梳理核心概念', '结合资料练习', '自测并复盘')
    steps = []
    for i in range(days):
        focus = topics[i % len(topics)] if topics else goal
        steps.append(StudyStep(day=i + 1, title=f'{focus}：{stages[min(i * 3 // days, 2)]}', minutes=minutes_per_day))
    return steps


def make_today_plan_options(
    goal: str,
    material_context: dict | None = None,
    daily_minutes: int | None = None,
    memory_blob: str = '',
) -> list[dict]:
    """Three 1-day intensity options; durations scale from preferred daily_minutes."""
    from .preferences_loop import parse_daily_minutes, plan_budgets_from_daily

    goal = grounded_goal(goal, material_context).strip() or '今日复习'
    topics = [t for t in ((material_context or {}).get('topics') or []) if str(t).strip()]
    focus = topics[0] if topics else goal
    secondary = topics[1] if len(topics) > 1 else focus
    budgets = plan_budgets_from_daily(parse_daily_minutes(str(daily_minutes) if daily_minutes is not None else '45'))
    light, standard, intensive = budgets['light'], budgets['standard'], budgets['intensive']
    # Fold personal goal/weak hints into titles when present (short).
    hint = ''
    if memory_blob:
        weak = re.search(r'薄弱点：([^；]+)', memory_blob)
        if weak and weak.group(1).strip() not in {'暂无', ''}:
            hint = f'（针对：{weak.group(1).strip()[:18]}）'
    read_min = max(10, intensive - 15)
    drill_min = max(10, intensive - read_min)
    return [
        {
            'key': 'light',
            'label': '轻量',
            'blurb': f'约 {light} 分钟，快速过重点',
            'minutes': light,
            'steps': [{'day': 1, 'title': f'速览《{focus}》核心要点与原文表述{hint}', 'minutes': light}],
        },
        {
            'key': 'standard',
            'label': '标准',
            'blurb': f'约 {standard} 分钟，精读核心',
            'minutes': standard,
            'steps': [{'day': 1, 'title': f'精读《{focus}》原理与关键信号/要点的原文描述{hint}', 'minutes': standard}],
        },
        {
            'key': 'intensive',
            'label': '加练',
            'blurb': f'约 {intensive} 分钟，精读 + 巩固',
            'minutes': intensive,
            'steps': [
                {'day': 1, 'title': f'精读《{focus}》核心原文{hint}', 'minutes': read_min},
                {'day': 1, 'title': f'对照《{secondary}》做一题巩固', 'minutes': drill_min},
            ],
        },
    ]
