from fastapi.testclient import TestClient
from app.agent.intent import explicit_intent
from app.agent.intent import StudyIntent
from app.agent.service import StudyAgent
from app.database import store
from app.main import app
import asyncio


def test_explicit_intent_routes_only_clear_commands():
    plan = explicit_intent('帮我制定复习数据库的学习计划，3天每天30分钟')
    assert plan.action == 'plan' and plan.goal == '数据库' and plan.days == 3 and plan.minutes_per_day == 30
    assert explicit_intent('重新安排未完成任务，2天每天60分钟').action == 'replan'
    assert explicit_intent('数据库索引有什么用途？').action == 'chat'
    assert explicit_intent('帮我制定复习数据库的学习计划，99天').action == 'chat'
    assert explicit_intent('帮我制定学习计划').goal == ''
    assert explicit_intent('怎么制定学习计划？').action == 'chat'
    assert explicit_intent('开始专注 25 分钟').action == 'focus'
    assert explicit_intent('今日小测').action == 'quiz'
    assert explicit_intent('开始复习 B+树').action == 'review'
    assert explicit_intent('复习数据库').action == 'chat'


def test_chat_plan_and_replan_need_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'intent.db'))
    client = TestClient(app)
    with client.websocket_connect('/ws/chat') as ws:
        ws.receive_json()
        ws.send_json({'type': 'message', 'text': '帮我制定复习数据库的学习计划，2天每天30分钟'})
        assert ws.receive_json()['state'] == 'thinking'
        assert ws.receive_json()['state'] == 'tool'
        event = ws.receive_json()
        assert event['kind'] == 'plan' and len(event['draft']['steps']) == 2
        assert client.get('/tasks').json() == []
        client.post(f"/plans/drafts/{event['draft']['id']}/confirm")
        before = client.get('/tasks').json()
        ws.send_json({'type': 'message', 'text': '重新安排未完成任务，2天每天60分钟'})
        assert ws.receive_json()['state'] == 'thinking'
        assert ws.receive_json()['state'] == 'tool'
        event = ws.receive_json()
        assert event['kind'] == 'replan' and len(event['draft']['schedule']) == 2
        assert client.get('/tasks').json() == before


def test_plan_followup_goal(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'followup.db'))
    with TestClient(app).websocket_connect('/ws/chat') as ws:
        ws.receive_json()
        ws.send_json({'type': 'message', 'text': '帮我制定学习计划'})
        assert ws.receive_json()['state'] == 'thinking'
        assert '学习目标' in ws.receive_json()['text']
        ws.send_json({'type': 'message', 'text': '数据库索引'})
        assert ws.receive_json()['state'] == 'thinking'
        assert ws.receive_json()['state'] == 'tool'
        assert ws.receive_json()['draft']['goal'] == '数据库索引'


def test_model_intent_contract_without_external_api(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    class FakeModel:
        def __init__(self, **kwargs):
            assert kwargs['temperature'] == 0
        def with_structured_output(self, schema, method=None):
            assert method == "function_calling"
            assert schema is StudyIntent
            return self
        async def ainvoke(self, messages):
            assert messages[-1] == ('user', '把没做完的任务重新安排一下')
            return StudyIntent(action='replan', days=2, minutes_per_day=60)
    monkeypatch.setattr('app.agent.service.ChatOpenAI', FakeModel)
    result = asyncio.run(StudyAgent(store.connect).detect_intent('把没做完的任务重新安排一下', []))
    assert result.action == 'replan' and result.days == 2
