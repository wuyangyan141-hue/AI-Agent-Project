"""A deterministic planning workflow that the Agent can call as a tool."""
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


def validate_plan(proposal: PlanProposal, days: int, minutes_per_day: int) -> list[StudyStep]:
    """Reject a plausible-looking plan that cannot fit the requested schedule."""
    if not 1 <= days <= 14 or not 15 <= minutes_per_day <= 240:
        raise ValueError('Invalid time budget')
    totals = {day: 0 for day in range(1, days + 1)}
    titles = set()
    for step in proposal.steps:
        if step.day not in totals or not step.title.strip():
            raise ValueError('Plan contains an invalid day or empty title')
        totals[step.day] += step.minutes
        title = step.title.strip().casefold()
        if title in titles:
            raise ValueError('Plan contains repeated tasks')
        titles.add(title)
    if any(total == 0 or total > minutes_per_day for total in totals.values()):
        raise ValueError('Plan must cover each day without exceeding the daily budget')
    return [StudyStep(day=step.day, title=step.title.strip(), minutes=step.minutes)
            for step in sorted(proposal.steps, key=lambda item: item.day)]


def make_study_plan(goal: str, days: int = 3, minutes_per_day: int = 45) -> list[StudyStep]:
    goal = goal.strip()
    if not goal or not 1 <= days <= 14 or not 15 <= minutes_per_day <= 240:
        raise ValueError('Invalid study goal or schedule')
    stages = ('梳理核心概念', '结合资料练习', '自测并复盘')
    return [StudyStep(day=i + 1, title=f'{goal}：{stages[min(i * 3 // days, 2)]}', minutes=minutes_per_day) for i in range(days)]
