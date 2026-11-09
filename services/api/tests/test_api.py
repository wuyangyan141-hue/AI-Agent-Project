from fastapi.testclient import TestClient
from app.main import app


def test_health():
    response = TestClient(app).get('/health').json()
    assert response['status'] == 'ok'
    assert response['agent_mode'] in {'demo', 'langchain'}


def test_chat_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'chat.db'))
    with TestClient(app).websocket_connect('/ws/chat') as ws:
        assert ws.receive_json()['state'] == 'idle'
        ws.send_json({'type': 'message', 'text': '复习数据库'})
        assert ws.receive_json()['state'] == 'thinking'
        assert '复习数据库' in ws.receive_json()['text']
        ws.send_json({'type': 'message', 'text': '  '})
        assert ws.receive_json()['type'] == 'error'


def test_chat_plan_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'plan-chat.db'))
    client = TestClient(app)
    with client.websocket_connect('/ws/chat') as ws:
        ws.receive_json()
        ws.send_json({'type': 'plan_request', 'payload': {'goal': '复习数据库', 'days': 2, 'minutes_per_day': 30}})
        assert ws.receive_json()['state'] == 'thinking'
        event = ws.receive_json()
        assert event['type'] == 'plan_draft'
        assert len(event['draft']['steps']) == 2
        assert client.get('/tasks').json() == []
        draft_id = event['draft']['id']
        ws.send_json({'type': 'plan_request', 'payload': {'goal': '', 'days': 2}})
        assert ws.receive_json()['type'] == 'error'
    assert len(client.post(f'/plans/drafts/{draft_id}/confirm').json()['task_ids']) == 2
    assert len(client.get('/tasks').json()) == 2


def test_tasks_and_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'data.db'))
    client = TestClient(app)
    item = client.post('/tasks', json={'title': '复习数据库'})
    assert item.status_code == 201
    task_id = item.json()['id']
    assert client.patch(f'/tasks/{task_id}', json={'done': True}).json()['done'] is True
    assert client.get('/tasks').json()[0]['done'] is True
    assert client.patch('/tasks/9999', json={'done': True}).status_code == 404
    assert client.post('/tasks', json={'title': '   '}).status_code == 422
    assert client.put('/preferences/pet_name', json={'value': '蓝鲸'}).status_code == 200
    assert client.get('/preferences/pet_name').json()['value'] == '蓝鲸'


def test_local_renderer_cors(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'cors.db'))
    response = TestClient(app).options('/tasks', headers={
        'Origin': 'http://127.0.0.1:5173',
        'Access-Control-Request-Method': 'POST',
    })
    assert response.headers['access-control-allow-origin'] == 'http://127.0.0.1:5173'
