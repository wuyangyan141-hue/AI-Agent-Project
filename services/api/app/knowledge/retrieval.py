from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from .embeddings import LocalLexicalEmbeddings, cosine, features


class SQLiteRetriever(BaseRetriever):
    """LangChain retriever over persisted, user-scoped document chunks."""
    database: Any
    embeddings: Any
    embedding_id: str
    user_id: str
    document_ids: list[str] | None = None
    k: int = 4
    min_score: float = 0.10

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        if self.document_ids == []:
            return []
        sql = (
            "SELECT c.*,d.filename FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
            "WHERE d.user_id=? AND d.status='ready' AND d.embedding_id=?"
        )
        params = [self.user_id, self.embedding_id]
        if self.document_ids:
            sql += " AND d.id IN (" + ",".join("?" for _ in self.document_ids) + ")"
            params.extend(self.document_ids)
        rows = self.database.all(sql, params)
        if not rows:
            return []
        query_vector = self.embeddings.embed_query(query)
        tokens = features(query)
        ranked = []
        for row in rows:
            score = cosine(query_vector, row["vector"])
            if isinstance(self.embeddings, LocalLexicalEmbeddings):
                overlap = tokens.intersection(features(row["content"]))
                if not overlap:
                    continue
                # Query coverage keeps short Chinese questions retrievable in long passages.
                score = 0.25 * score + 0.75 * len(overlap) / max(1, len(tokens))
            if score >= self.min_score:
                ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [Document(page_content=row["content"], metadata={
            "chunk_id": row["id"], "document_id": row["document_id"], "filename": row["filename"],
            "page": row["page"], "section": row["section"], "score": round(score, 4),
        }) for score, row in ranked[:self.k]]
