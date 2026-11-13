"""One shared knowledge service per database/configuration, resolved lazily for tests."""
from functools import lru_cache
from .config import Settings
from .service import KnowledgeService


@lru_cache(maxsize=8)
def _service(settings: Settings):
    return KnowledgeService(settings)


def get_knowledge() -> KnowledgeService:
    from ..runtime_llm import active_settings
    return _service(active_settings())


def personal_context(query: str) -> dict:
    knowledge = get_knowledge()
    return {
        'preferences': knowledge.preferences('local-user'),
        'memories': knowledge.search_memories('local-user', query),
    }
