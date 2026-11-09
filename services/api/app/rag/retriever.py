"""Local document retrieval contract; implementations must return source metadata."""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Passage:
    text: str
    source: str

class Retriever(Protocol):
    async def search(self, query: str, limit: int = 5) -> list[Passage]: ...
