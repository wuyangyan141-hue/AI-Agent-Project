import pytest

@pytest.fixture(autouse=True)
def isolated_backend(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'test.db'))
    monkeypatch.setenv('KNOWLEDGE_DATA_DIR',str(tmp_path/'knowledge'))
    for key in ['OPENAI_API_KEY','LLM_API_KEY','DASHSCOPE_API_KEY','LLM_MODEL','LLM_BASE_URL','OPENAI_BASE_URL','AGENT_MODEL','EMBEDDING_PROVIDER','EMBEDDING_MODEL','EMBEDDING_API_KEY','EMBEDDING_BASE_URL']:
        monkeypatch.delenv(key,raising=False)
    from app.knowledge.integration import _service
    _service.cache_clear()
    yield
    _service.cache_clear()
