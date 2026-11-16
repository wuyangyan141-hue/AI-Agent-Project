"""HITL form schemas for the desktop UI."""
from __future__ import annotations

QUIZ_HITL_SCHEMA = {
    'kind': 'quiz_params',
    'title': '小测设置',
    'fields': [
        {
            'key': 'limit',
            'label': '题目数量',
            'type': 'select',
            'options': [
                {'value': '1', 'label': '1 道'},
                {'value': '2', 'label': '2 道'},
                {'value': '3', 'label': '3 道（默认）'},
                {'value': '4', 'label': '4 道'},
                {'value': '5', 'label': '5 道'},
            ],
            'default': '3',
        },
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
        {
            'key': 'days',
            'label': '计划天数',
            'type': 'select',
            'options': [
                {'value': '2', 'label': '2 天'},
                {'value': '3', 'label': '3 天（常用）'},
                {'value': '5', 'label': '5 天'},
                {'value': '7', 'label': '1 周'},
                {'value': '14', 'label': '2 周'},
            ],
            'default': '3',
        },
        {
            'key': 'minutes_per_day',
            'label': '每天可用时间',
            'type': 'select',
            'options': [
                {'value': '30', 'label': '30 分钟'},
                {'value': '45', 'label': '45 分钟（常用）'},
                {'value': '60', 'label': '60 分钟'},
                {'value': '90', 'label': '90 分钟'},
            ],
            'default': '45',
        },
    ],
}

PLAN_REVISE_HITL_SCHEMA = {
    'kind': 'plan_revise',
    'title': '确认或修改计划',
    'fields': [
        {'key': 'goal', 'label': '学习目标', 'type': 'text', 'maxLength': 200},
        {
            'key': 'days',
            'label': '计划天数',
            'type': 'select',
            'options': [
                {'value': '2', 'label': '2 天'},
                {'value': '3', 'label': '3 天'},
                {'value': '5', 'label': '5 天'},
                {'value': '7', 'label': '1 周'},
                {'value': '14', 'label': '2 周'},
            ],
            'default': '3',
        },
        {
            'key': 'minutes_per_day',
            'label': '每天可用时间',
            'type': 'select',
            'options': [
                {'value': '30', 'label': '30 分钟'},
                {'value': '45', 'label': '45 分钟'},
                {'value': '60', 'label': '60 分钟'},
                {'value': '90', 'label': '90 分钟'},
            ],
            'default': '45',
        },
        {
            'key': 'revision',
            'label': '修改意见（可选）',
            'type': 'textarea',
            'maxLength': 800,
            'placeholder': '例如：第 2 天改成做练习题；减少重复阅读…',
        },
    ],
}