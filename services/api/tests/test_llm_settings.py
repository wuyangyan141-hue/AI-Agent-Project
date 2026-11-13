from fastapi.testclient import TestClient
from app.main import app, agent
from app.runtime_llm import apply_runtime, public_config, save_config


def test_llm_settings_offline_and_online_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'llm.db'))
    for key in ['OPENAI_API_KEY', 'LLM_API_KEY', 'DASHSCOPE_API_KEY', 'LLM_MODEL', 'AGENT_MODEL']:
        monkeypatch.delenv(key, raising=False)
    client = TestClient(app)
    offline = client.put('/settings/llm', json={'mode': 'offline'}).json()
    assert offline['mode'] == 'offline'
    assert offline['agent_mode'] == 'demo'
    assert agent.mode == 'demo'

    bad = client.put('/settings/llm', json={
        'mode': 'online', 'llm_model': '', 'llm_base_url': 'https://example.com/v1', 'llm_api_key': 'sk-x',
    })
    assert bad.status_code == 422

    online = client.put('/settings/llm', json={
        'mode': 'online',
        'provider': 'custom',
        'llm_model': 'qwen-plus',
        'llm_base_url': 'https://example.com/v1',
        'llm_api_key': 'sk-test-key-12345678',
    }).json()
    assert online['mode'] == 'online'
    assert online['online_ready'] is True
    assert online['has_api_key'] is True
    assert '*' in online['api_key_masked']
    assert 'sk-test-key-12345678' not in online['api_key_masked']
    assert agent.mode == 'langchain'

    # Blank / masked key keeps the previously saved secret.
    kept = client.put('/settings/llm', json={
        'mode': 'online',
        'llm_model': 'qwen-plus',
        'llm_base_url': 'https://example.com/v1',
        'llm_api_key': 'sk-****5678',
    }).json()
    assert kept['has_api_key'] is True
    assert client.get('/settings/llm').json()['online_ready'] is True


def test_save_config_requires_https_url(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'llm2.db'))
    try:
        save_config({
            'mode': 'online',
            'llm_model': 'm',
            'llm_api_key': 'k',
            'llm_base_url': 'not-a-url',
        })
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert 'http' in str(exc)
    apply_runtime(agent)
    assert public_config()['mode'] in {'offline', 'online'}
