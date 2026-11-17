from fastapi.testclient import TestClient

from app.main import app


def test_clear_sessions_keeps_learning_folder():
    client = TestClient(app)

    project = client.post('/knowledge/projects', json={'name': '期末复习'}).json()
    session_id = project['session_id']
    client.post('/knowledge/chat', json={'question': '你好豆豆', 'session_id': session_id})
    assert client.get(f'/knowledge/sessions/{session_id}/messages').json()

    cleared = client.delete('/knowledge/sessions').json()
    assert cleared['total'] >= 1
    assert cleared['cleared_messages_sessions'] >= 1

    projects = client.get('/knowledge/projects').json()
    assert any(p['id'] == project['id'] for p in projects)
    assert client.get(f'/knowledge/sessions/{session_id}/messages').json() == []


def test_reset_local_data_requires_confirm_and_rebuilds_default():
    client = TestClient(app)

    client.post('/knowledge/projects', json={'name': '临时夹'})
    client.post('/tasks', json={'title': '刷题'})
    denied = client.post('/knowledge/data/reset', json={'confirm': 'nope', 'keep_preferences': True})
    assert denied.status_code == 422

    result = client.post('/knowledge/data/reset', json={'confirm': 'RESET', 'keep_preferences': True}).json()
    assert result['preferences_kept'] is True
    projects = client.get('/knowledge/projects').json()
    assert len(projects) == 1
    assert projects[0]['name'] == '默认学习'
    assert client.get('/tasks').json() == []
