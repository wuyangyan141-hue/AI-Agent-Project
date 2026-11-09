from fastapi.testclient import TestClient
from app.main import app

def test_health():
    assert TestClient(app).get('/health').json() == {'status': 'ok'}

def test_chat_roundtrip():
    with TestClient(app).websocket_connect('/ws/chat') as ws:
        assert ws.receive_json()['type'] == 'welcome'
        ws.send_json({'type': 'message', 'text': '复习数据库'})
        assert '复习数据库' in ws.receive_json()['text']
        ws.send_json({'type': 'message', 'text': '  '})
        assert ws.receive_json()['type'] == 'error'
