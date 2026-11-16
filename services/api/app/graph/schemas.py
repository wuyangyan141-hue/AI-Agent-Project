"""HITL form schemas for the desktop UI."""
from __future__ import annotations

QUIZ_HITL_SCHEMA = {
    'kind': 'quiz_params',
    'title': '小测设置',
    'fields': [
        {'key': 'limit', 'label': '题目数量', 'type': 'number', 'min': 1, 'max': 5, 'default': 3},
        {
            'key': 'difficulty',
            'label': '难度',
            'type': 'select',
            'options': [
                {'value': 'easy', 'label': '轻松（偏判断/单选）'},
                {'value': 'standard', 'label': '标准（题型轮换）'},
                {'value': 'hard', 'label': '进阶（简答/对比增多）'},
            ],
            'default': 'standard',
        },
    ],
}

PLAN_HITL_SCHEMA = {
    'kind': 'plan_params',
    'title': '学习计划参数',
    'fields': [
        {'key': 'goal', 'label': '学习目标', 'type': 'text', 'maxLength': 200},
        {'key': 'days', 'label': '计划天数', 'type': 'number', 'min': 1, 'max': 14, 'default': 3},
        {'key': 'minutes_per_day', 'label': '每天分钟', 'type': 'number', 'min': 15, 'max': 240, 'default': 45},
    ],
}