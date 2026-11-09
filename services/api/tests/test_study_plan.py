import pytest
from app.skills.study_plan import make_study_plan


def test_plan_has_daily_steps():
    plan = make_study_plan('数据库索引', 3, 40)
    assert [step.day for step in plan] == [1, 2, 3]
    assert all('数据库索引' in step.title and step.minutes == 40 for step in plan)


def test_invalid_schedule():
    with pytest.raises(ValueError):
        make_study_plan('', 3)
