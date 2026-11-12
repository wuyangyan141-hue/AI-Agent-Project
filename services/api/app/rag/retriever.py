"""Local document retrieval contract; implementations must return source metadata."""
from dataclasses import dataclass
from typing import Protocol
import asyncio
from ..knowledge.retrieval import SQLiteRetriever

@dataclass(frozen=True)
class Passage:
    text: str
    source: str

class Retriever(Protocol):
    async def search(self, query: str, limit: int = 5) -> list[Passage]: ...


class LocalDocumentRetriever:
    """The original member-2 contract, now backed by LangChain/SQLite."""
    async def search(self, query: str, limit: int = 5) -> list[Passage]:
        from ..knowledge.integration import get_knowledge
        results = await asyncio.to_thread(get_knowledge().search,'local-user',query,None,limit)
        return [Passage(text=item['snippet'],source=f"{item['filename']} · "+(f"第{item['page']}页" if item['page'] else item['section'])) for item in results]
