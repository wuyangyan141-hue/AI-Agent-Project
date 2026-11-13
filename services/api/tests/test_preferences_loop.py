from app.skills.preferences_loop import (
    plan_budgets_from_daily,
    parse_daily_minutes,
    parse_study_hm,
    rebuild_preference_summary,
)


def test_parse_daily_and_study_window():
    assert parse_daily_minutes('60') == 60
    assert parse_daily_minutes('每天约 40 分钟') == 40
    assert parse_study_hm('20:00–21:00') == (20, 0)
    assert parse_study_hm('晚上8:30') == (8, 30)


def test_budgets_and_summary():
    budgets = plan_budgets_from_daily(60)
    assert budgets['light'] < budgets['standard'] <= budgets['intensive']
    summary = rebuild_preference_summary(
        {'daily_minutes': '60', 'study_time': '20:00', 'explanation_style': '先讲结论'},
        {
            '目标': {'content': '吃透双MACD'},
            '薄弱点': {'content': '回调与突破'},
            '忌讳': {'content': '别堆术语'},
        },
    )
    assert '60' in summary and '20:00' in summary and '先讲结论' in summary
    assert '吃透双MACD' in summary and '回调与突破' in summary
