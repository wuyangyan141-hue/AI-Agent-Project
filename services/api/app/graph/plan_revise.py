"""Plan draft review / regenerate HITL helpers."""
from __future__ import annotations

from .schemas import PLAN_REVISE_HITL_SCHEMA


def format_plan_preview(steps: list[dict] | None) -> str:
    if not steps:
        return '（暂无步骤预览）'
    lines: list[str] = []
    for step in steps[:20]:
        day = step.get('day') or step.get('scheduled_day') or '?'
        title = (step.get('title') or '').strip() or '未命名任务'
        minutes = step.get('minutes')
        suffix = f' · {minutes} 分钟' if minutes is not None else ''
        lines.append(f'第{day}天：{title}{suffix}')
    if len(steps) > 20:
        lines.append(f'…共 {len(steps)} 项')
    return '\n'.join(lines)


def infer_plan_days(steps: list[dict] | None, fallback: int = 3) -> int:
    if not steps:
        return fallback
    days = [int(s.get('day') or s.get('scheduled_day') or 1) for s in steps]
    return max(days) if days else fallback


def infer_daily_minutes(steps: list[dict] | None, fallback: int = 45) -> int:
    if not steps:
        return fallback
    by_day: dict[int, int] = {}
    for step in steps:
        day = int(step.get('day') or step.get('scheduled_day') or 1)
        by_day[day] = by_day.get(day, 0) + int(step.get('minutes') or 0)
    if not by_day:
        return fallback
    return max(by_day.values())


def plan_revise_hitl(draft: dict, plan_kind: str) -> dict:
    steps = draft.get('steps') or draft.get('schedule') or []
    return {
        **PLAN_REVISE_HITL_SCHEMA,
        'preview': format_plan_preview(steps),
        'defaults': {
            'draft_id': draft['id'],
            'goal': (draft.get('goal') or '').strip(),
            'days': infer_plan_days(steps if isinstance(steps, list) else None),
            'minutes_per_day': infer_daily_minutes(steps if isinstance(steps, list) else None),
            'revision': '',
            'plan_kind': plan_kind,
        },
    }