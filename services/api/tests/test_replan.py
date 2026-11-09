from fastapi.testclient import TestClient
from app.main import app


def test_replan_requires_confirmation_and_respects_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'replan.db'))
    client = TestClient(app)
    first = client.post('/tasks', json={'title': 'B+树'}).json()
    second = client.post('/tasks', json={'title': 'Hash索引'}).json()
    draft = client.post('/plans/replan-drafts', json={'days': 2, 'minutes_per_day': 30})
    assert draft.status_code == 201
    assert [item['day'] for item in draft.json()['schedule']] == [1, 2]
    assert all(item['scheduled_day'] is None for item in client.get('/tasks').json())
    confirmed = client.post(f"/plans/replan-drafts/{draft.json()['id']}/confirm")
    assert confirmed.status_code == 200
    tasks = {item['id']: item for item in client.get('/tasks').json()}
    assert tasks[first['id']]['scheduled_day'] == 1
    assert tasks[second['id']]['scheduled_day'] == 2
    assert client.post(f"/plans/replan-drafts/{draft.json()['id']}/confirm").status_code == 409


def test_replan_rejects_impossible_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'replan.db'))
    client = TestClient(app)
    client.post('/tasks', json={'title': 'A'})
    client.post('/tasks', json={'title': 'B'})
    assert client.post('/plans/replan-drafts', json={'days': 1, 'minutes_per_day': 30}).status_code == 422
