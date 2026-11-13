from fastapi.testclient import TestClient

from app.main import app


def test_soft_delete_restore_and_completion_bones(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'tasks.db'))
    client = TestClient(app)

    created = client.post('/tasks', json={'title': '复习双MACD', 'estimated_minutes': 45}).json()
    task_id = created['id']
    assert client.get('/tasks').json()[0]['id'] == task_id

    deleted = client.delete(f'/tasks/{task_id}').json()
    assert deleted['deleted'] is True
    assert client.get('/tasks').json() == []
    trash = client.get('/tasks/trash').json()
    assert len(trash) == 1 and trash[0]['id'] == task_id

    restored = client.post(f'/tasks/{task_id}/restore').json()
    assert restored['deleted_at'] is None
    assert client.get('/tasks').json()[0]['id'] == task_id
    assert client.get('/tasks/trash').json() == []

    done = client.patch(f'/tasks/{task_id}', json={'done': True}).json()
    assert done['done'] is True
    assert done['bones_awarded'] is True
    assert done['reward']['bones_earned'] == 3  # 45 / 15
    assert done['reward']['bones'] == 3
    assert 'first_task' in done['reward']['new_achievements']
    assert done['reward']['speech']
    assert '骨头' in done['reward']['speech']
    assert '复习双MACD' in done['reward']['speech']

    streak = client.get('/learning/streak').json()
    assert streak['bones'] == 3
    assert streak['tasks_completed'] == 1
    assert streak['feed_cost'] == 3

    # Uncheck then complete again must NOT award bones a second time.
    client.patch(f'/tasks/{task_id}', json={'done': False})
    again = client.patch(f'/tasks/{task_id}', json={'done': True}).json()
    assert again.get('reward') is None
    assert again['bones_awarded'] is True
    assert client.get('/learning/streak').json()['bones'] == 3

    fed = client.post('/learning/bones/feed').json()
    assert fed['ok'] is True and fed['cost'] == 3 and fed['bones'] == 0
    assert fed['speech'] and '（花费' not in fed['speech']
    assert fed['speech'] in fed['message']
    assert client.get('/learning/streak').json()['pet_feeds'] == 1
    assert client.post('/learning/bones/feed').status_code == 422

    client.delete(f'/tasks/{task_id}')
    purged = client.delete(f'/tasks/{task_id}/purge').json()
    assert purged['purged'] is True
    assert client.get('/tasks/trash').json() == []


def test_focus_finish_completes_task_and_awards_bones(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'focus_checkin.db'))
    client = TestClient(app)

    task = client.post('/tasks', json={'title': '精读双MACD原文', 'estimated_minutes': 30}).json()
    focus = client.post('/focus', json={'task_id': task['id'], 'minutes': 0.05}).json()
    assert focus['task_id'] == task['id']
    status = client.get('/focus').json()
    assert status['id'] == focus['id']
    assert status['task_title'] == '精读双MACD原文'

    done = client.post(f"/focus/{focus['id']}/finish").json()
    assert done['finished'] is True
    assert done['task_id'] == task['id']
    assert done['task']['done'] is True
    assert done['reward']['bones_earned'] >= 1
    assert done['speech'] and '骨头' in done['speech']
    assert client.get('/tasks').json()[0]['done'] is True
    assert client.get('/learning/streak').json()['bones'] == done['reward']['bones']
