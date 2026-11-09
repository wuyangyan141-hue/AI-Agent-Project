"""A deterministic planning workflow that the Agent can call as a tool."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StudyStep:
    day: int
    title: str
    minutes: int


def make_study_plan(goal: str, days: int = 3, minutes_per_day: int = 45) -> list[StudyStep]:
    goal = goal.strip()
    if not goal or not 1 <= days <= 14 or not 15 <= minutes_per_day <= 240:
        raise ValueError('Invalid study goal or schedule')
    stages = ('梳理核心概念', '结合资料练习', '自测并复盘')
    return [StudyStep(day=i + 1, title=f'{goal}：{stages[min(i * 3 // days, 2)]}', minutes=minutes_per_day) for i in range(days)]
