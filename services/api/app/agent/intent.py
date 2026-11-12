"""Route a study request to a confirmation workflow or ordinary chat."""
import re
from typing import Literal

from pydantic import BaseModel, Field


class StudyIntent(BaseModel):
    action: Literal['chat', 'plan', 'replan', 'focus', 'review', 'quiz', 'weak', 'next'] = 'chat'
    goal: str = Field(default='', max_length=200)
    days: int = Field(default=3, ge=1, le=14)
    minutes_per_day: int = Field(default=45, ge=15, le=240)
    minutes: int = Field(default=25, ge=1, le=240)
    topic: str = Field(default='', max_length=200)


def explicit_intent(text: str) -> StudyIntent:
    """Conservative fallback: only route an unmistakable plan/focus/review command."""
    days_match = re.search(r'(\d{1,2})\s*天', text)
    minutes_match = re.search(r'每天\s*(\d{1,3})\s*分钟', text)
    days = int(days_match.group(1)) if days_match else 3
    minutes = int(minutes_match.group(1)) if minutes_match else 45

    # Plan / replan first so “制定复习…计划” is not eaten by review.
    if 1 <= days <= 14 and 15 <= minutes <= 240:
        if re.search(r'(重新|重排|调整).{0,10}(未完成|剩余|没做完).{0,10}(任务|计划)', text):
            return StudyIntent(action='replan', days=days, minutes_per_day=minutes)
        match = re.search(
            r'(?:帮我|请|给我)?\s*(?:制定|生成|安排|规划)\s*(?:一个|一份)?\s*(.{1,160}?)\s*(?:的)?\s*(?:学习)?计划',
            text,
        )
        if match:
            goal = re.sub(r'^(?:学习|复习|关于)\s*', '', match.group(1)).strip(' ：:，,')
            goal = re.sub(r'\s*\d{1,2}\s*天.*$', '', goal).strip()
            if goal:
                return StudyIntent(action='plan', goal=goal, days=days, minutes_per_day=minutes)
        if re.match(r'^\s*(?:(?:请|帮我|给我)\s*)*(?:制定|生成|安排|规划).{0,8}(?:学习)?计划', text):
            return StudyIntent(action='plan', days=days, minutes_per_day=minutes)

    focus_match = re.search(r'(?:开始|进入)?专注\s*(\d{1,3})\s*分钟', text)
    if focus_match or re.search(r'开始专注|进入番茄|开始番茄', text):
        focus_minutes = int(focus_match.group(1)) if focus_match else 25
        if 1 <= focus_minutes <= 240:
            return StudyIntent(action='focus', minutes=focus_minutes)
    if re.search(r'今日小测|今天小测|来几道题|小测验|我想小测|我要小测|小测一下|开始小测|来个小测|做个小测', text):
        return StudyIntent(action='quiz')
    if re.search(r'薄弱点|薄弱环节|错题回顾|回顾薄弱', text):
        return StudyIntent(action='weak')
    if re.search(
        r'下一步|接下来做什么|学习闭环|继续学习|该学什么|该做什么|怎么办|卡住了|帮我想想|不知道学什么|推荐下一步|我该怎么学',
        text,
    ):
        return StudyIntent(action='next')
    # “我来回答复习题” is a coach prompt echo — not a command to start a new review.
    if re.search(r'我来回答|直接作答|提交答案|这是我的回答', text):
        return StudyIntent()
    if re.search(r'开始复习|来一题复习|做一题复习|交互式复习|复习一下|我想复习|我要复习|复习题', text):
        topic_match = re.search(r'(?:开始复习|来一题复习|做一题复习|复习一下|复习题)\s*(.+)$', text)
        topic = ''
        if topic_match:
            topic = topic_match.group(1).strip(' ：:，,。.!！？?')
            topic = re.sub(r'^(?:一下|今天|今日|知识点|题目)?', '', topic).strip()
            topic = re.sub(r'^：\s*', '', topic).strip()
        if topic in {'重点', '今日重点', '知识点'}:
            topic = '今日重点'
        return StudyIntent(action='review', topic=topic or '今日重点')
    return StudyIntent()
