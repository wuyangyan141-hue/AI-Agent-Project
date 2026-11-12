import pytest
from app.skills.study_plan import make_study_plan, PlanProposal, validate_plan
from app.agent.service import StudyAgent
from app.database import store
import asyncio


def test_plan_has_daily_steps():
    plan = make_study_plan('数据库索引', 3, 40)
    assert [step.day for step in plan] == [1, 2, 3]
    assert all('数据库索引' in step.title and step.minutes == 40 for step in plan)


def test_invalid_schedule():
    with pytest.raises(ValueError):
        make_study_plan('', 3)


def test_model_plan_must_cover_days_and_fit_budget():
    valid = PlanProposal(steps=[
        {'day': 1, 'title': '阅读索引原理', 'minutes': 20},
        {'day': 1, 'title': '画 B+ 树', 'minutes': 25},
        {'day': 2, 'title': '练习范围查询', 'minutes': 35},
    ])
    assert [step.day for step in validate_plan(valid, 2, 45)] == [1, 1, 2]
    with pytest.raises(ValueError, match='daily budget'):
        validate_plan(valid, 2, 40)
    with pytest.raises(ValueError, match='cover each day'):
        validate_plan(valid, 3, 45)
    with pytest.raises(ValueError, match='repeated'):
        validate_plan(PlanProposal(steps=[
            {'day': 1, 'title': '复习', 'minutes': 20},
            {'day': 2, 'title': '复习', 'minutes': 20},
        ]), 2, 45)


def test_model_plan_is_structured_and_validated(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    class FakeModel:
        def __init__(self, **kwargs):
            assert kwargs['temperature'] == 0
        def with_structured_output(self, schema, method=None):
            assert method == "function_calling"
            assert schema is PlanProposal
            return self
        async def ainvoke(self, messages):
            assert '数据库索引' in messages[-1][1]
            return PlanProposal(steps=[
                {'day': 1, 'title': '理解 B+ 树', 'minutes': 30},
                {'day': 2, 'title': '索引练习', 'minutes': 30},
            ])
    monkeypatch.setattr('app.agent.service.ChatOpenAI', FakeModel)
    plan = asyncio.run(StudyAgent(store.connect).generate_plan('数据库索引', 2, 45))
    assert [step.title for step in plan] == ['理解 B+ 树', '索引练习']
