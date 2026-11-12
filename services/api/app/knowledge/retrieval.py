"""Keyword + semantic retrieval. Empty evidence is a valid result."""
import math
import re
from collections import Counter
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from .embeddings import LocalLexicalEmbeddings, cosine

STOP = set("the a an and or is are was were to of in on for with what why how explain describe please this that it does do be can".split())
ZH_STOP = {'这个','这些','什么','为何','为什么','怎么','如何','请问','解释','一下','资料','文档','讲义','主要','哪些','是否','可以','根据','它的','中的','告诉','我们','一下子'}


def terms(text):
    result = [w for w in re.findall(r'[a-z0-9][a-z0-9_+-]*', text.lower()) if w not in STOP and len(w) > 1]
    clean = text
    for word in sorted(ZH_STOP, key=len, reverse=True):
        clean = clean.replace(word, ' ')
    for run in re.findall(r'[\u3400-\u9fff]+', clean):
        if len(run) == 1:
            continue
        result.extend(run[i:i+2] for i in range(len(run)-1))
    return result


class SQLiteRetriever(BaseRetriever):
    database: Any
    embeddings: Any
    embedding_id: str
    user_id: str
    document_ids: list[str] | None = None
    k: int = 4
    min_score: float = 0.16
    semantic_min_score: float = 0.45

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        if self.document_ids == [] or not query.strip():
            return []
        sql = ("SELECT c.*,d.filename FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
               "WHERE d.user_id=? AND d.status='ready' AND d.embedding_id=?")
        params = [self.user_id, self.embedding_id]
        if self.document_ids:
            sql += ' AND d.id IN (' + ','.join('?' for _ in self.document_ids) + ')'
            params.extend(self.document_ids)
        rows = self.database.all(sql, params)
        if not rows:
            return []
        query_terms = set(terms(query))
        bags = [Counter(terms(row['content'])) for row in rows]
        avg_len = sum(sum(bag.values()) for bag in bags) / max(1, len(bags))
        dfs = Counter(t for bag in bags for t in bag)
        semantic = not isinstance(self.embeddings, LocalLexicalEmbeddings)
        query_vector = self.embeddings.embed_query(query) if semantic else None
        ranked = []
        for row, bag in zip(rows, bags):
            overlap = query_terms.intersection(bag)
            coverage = len(overlap) / max(1, len(query_terms))
            bm25 = 0.0
            for token in overlap:
                tf = bag[token]
                idf = math.log(1 + (len(rows) - dfs[token] + .5) / (dfs[token] + .5))
                bm25 += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * sum(bag.values()) / max(1, avg_len)))
            lexical = coverage * (0.7 + 0.3 * bm25 / (1 + bm25)) if overlap else 0.0
            dense = cosine(query_vector, row['vector']) if semantic else 0.0
            # Hash collisions and filename-only matches cannot create evidence.
            if lexical < self.min_score and (not semantic or dense < self.semantic_min_score):
                continue
            score = max(lexical, dense) if semantic else lexical
            fused = (0.65 * dense + 0.35 * lexical) if semantic else lexical
            ranked.append((fused, score, lexical, dense, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        chosen, fingerprints = [], set()
        for _, score, lexical, dense, row in ranked:
            fingerprint = (row['document_id'], re.sub(r'\s+', ' ', row['content']).strip())
            if fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            chosen.append(Document(page_content=row['content'], metadata={
                'chunk_id': row['id'], 'document_id': row['document_id'], 'filename': row['filename'],
                'page': row['page'], 'section': row['section'], 'score': round(score, 4),
                'lexical_score': round(lexical, 4), 'semantic_score': round(dense, 4),
                'retrieval_method': 'hybrid' if semantic else 'bm25', 'evidence_kind': 'retrieved',
            }))
            if len(chosen) >= self.k:
                break
        return chosen
