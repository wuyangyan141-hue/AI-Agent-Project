from fastapi.testclient import TestClient
from app.main import app
from app.mcp.server import create_study_task, complete_study_task, start_focus_timer, get_focus_timer
from app.agent.service import ToolStatusHandler
import asyncio


def test_plan_review_focus_and_task_edit(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'flow.db'))
    client = TestClient(app)
    draft = client.post('/plans/drafts', json={'goal':'复习数据库', 'days':3, 'minutes_per_day':40})
    assert draft.status_code == 201
    assert client.get('/tasks').json() == []
    draft_id = draft.json()['id']
    assert len(client.post(f'/plans/drafts/{draft_id}/confirm').json()['task_ids']) == 3
    assert client.post(f'/plans/drafts/{draft_id}/confirm').status_code == 409
    task = client.get('/tasks').json()[0]
    updated = client.patch(f"/tasks/{task['id']}", json={'title':'复习 B+ 树', 'estimated_minutes':20, 'done':True})
    assert updated.json()['done'] is True
    assert updated.json()['estimated_minutes'] == 20
    focus = client.post('/focus', json={'task_id':task['id'], 'minutes':1})
    assert focus.status_code == 201
    assert client.post('/focus', json={'minutes':1}).status_code == 409
    assert client.get('/focus').json()['remaining_seconds'] > 0
    assert client.post(f"/focus/{focus.json()['id']}/finish").status_code == 200
    review = client.post('/reviews', json={'topic':'B+树'}).json()
    response = client.post(f"/reviews/{review['id']}/answer", json={'answer':'叶子节点有链表连接'})
    assert response.json()['result'] == 'correct'
    assert client.post(f"/reviews/{review['id']}/answer", json={'answer':'再试'}).status_code == 409


def test_mcp_tool_success_cases(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'mcp.db'))
    scenarios = [
        lambda: create_study_task('数据库', 20)['title'] == '数据库',
        lambda: complete_study_task(1)['done'] is True,
        lambda: start_focus_timer(1, 1)['task_id'] == 1,
        lambda: get_focus_timer()['remaining_seconds'] > 0,
    ]
    successes = [case() for case in scenarios]
    assert sum(successes) / len(scenarios) == 1.0


def test_tool_start_emits_execution_state():
    events = []
    async def emit(state, message):
        events.append((state, message))
    asyncio.run(ToolStatusHandler(emit).on_tool_start({'name': 'preview_study_plan'}, '{}'))
    assert events == [('tool', '正在调用工具：preview_study_plan')]
