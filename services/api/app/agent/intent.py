"""Route a study request to a confirmation workflow or ordinary chat."""
import re
from typing import Literal

from pydantic import BaseModel, Field


class StudyIntent(BaseModel):
    action: Literal['chat', 'plan', 'replan'] = 'chat'
    goal: str = Field(default='', max_length=200)
    days: int = Field(default=3, ge=1, le=14)
    minutes_per_day: int = Field(default=45, ge=15, le=240)


def explicit_intent(text: str) -> StudyIntent:
    """Conservative fallback: only route an unmistakable plan command."""
    days_match = re.search(r'(\d{1,2})\s*天', text)
    minutes_match = re.search(r'每天\s*(\d{1,3})\s*分钟', text)
    days = int(days_match.group(1)) if days_match else 3
    minutes = int(minutes_match.group(1)) if minutes_match else 45
    if not 1 <= days <= 14 or not 15 <= minutes <= 240:
        return StudyIntent()
    if re.search(r'(重新|重排|调整).{0,10}(未完成|剩余|没做完).{0,10}(任务|计划)', text):
        return StudyIntent(action='replan', days=days, minutes_per_day=minutes)
    match = re.search(r'(?:帮我|请|给我)?\s*(?:制定|生成|安排|规划)\s*(?:一个|一份)?\s*(.{1,160}?)\s*(?:的)?\s*(?:学习)?计划', text)
    if match:
        goal = re.sub(r'^(?:学习|复习|关于)\s*', '', match.group(1)).strip(' ：:，,')
        goal = re.sub(r'\s*\d{1,2}\s*天.*$', '', goal).strip()
        if goal:
            return StudyIntent(action='plan', goal=goal, days=days, minutes_per_day=minutes)
    if re.search(r'(?:制定|生成|安排|规划).{0,8}(?:学习)?计划', text):
        return StudyIntent(action='plan', days=days, minutes_per_day=minutes)
    return StudyIntent()
