"""Lexical retrieval helpers used by the local knowledge base."""
from app.knowledge.embeddings import LocalLexicalEmbeddings, features
from app.knowledge.retrieval import SQLiteRetriever


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def all(self, sql, params):
        return self._rows


def test_features_include_chinese_unigrams():
    tokens = features('这份报告讲什么')
    assert '报' in tokens and '报告' in tokens
    assert 'report' in features('midterm report pages')


def test_weak_cosine_without_overlap_is_filtered():
    encoder = LocalLexicalEmbeddings()
    content = (
        'The midterm report requires a project objective and grading criteria '
        'for the team submission.'
    )
    row = {
        'id': 'c1', 'document_id': 'd1', 'filename': 'guide.pdf',
        'page': 1, 'section': 'Overview', 'content': content,
        'vector': encoder.embed_query(content),
    }

    class WeakEmb(LocalLexicalEmbeddings):
        def embed_query(self, text: str):
            # Force near-orthogonal vectors so soft-hit cannot fire on collisions alone.
            if text == content:
                return list(row['vector'])
            return [0.0] * self.dimension

    retriever = SQLiteRetriever(
        database=_FakeDb([row]), embeddings=WeakEmb(), embedding_id='test',
        user_id='u', k=3, min_score=0.10, semantic_min_score=0.45,
    )
    docs = retriever.invoke('完全不同的中文短问')
    assert docs == []


def test_strong_cosine_soft_hit_without_token_overlap():
    encoder = LocalLexicalEmbeddings()
    content = (
        'The midterm report requires a project objective and grading criteria '
        'for the team submission.'
    )
    vector = encoder.embed_query(content)
    row = {
        'id': 'c1', 'document_id': 'd1', 'filename': 'guide.pdf',
        'page': 1, 'section': 'Overview', 'content': content,
        'vector': vector,
    }

    class FixedEmb(LocalLexicalEmbeddings):
        def embed_query(self, text: str):
            return list(vector)

    # True semantic / test embeddings may soft-hit without lexical overlap.
    retriever = SQLiteRetriever(
        database=_FakeDb([row]), embeddings=FixedEmb(), embedding_id='test',
        user_id='u', k=3, min_score=0.10, semantic_min_score=0.45,
    )
    docs = retriever.invoke('完全不同的中文短问')
    assert docs and docs[0].metadata['retrieval_method'] == 'semantic'

    # Local feature-hash must NOT treat collision soft-hits as evidence.
    local = SQLiteRetriever(
        database=_FakeDb([row]), embeddings=FixedEmb(), embedding_id='lexical-hash-v2-2048',
        user_id='u', k=3, min_score=0.10, semantic_min_score=0.45,
    )
    assert local.invoke('完全不同的中文短问') == []


def test_filename_boost_helps_mixed_query():
    encoder = LocalLexicalEmbeddings()
    content = 'Students must submit the midterm report with grading criteria listed below.'
    row = {
        'id': 'c1', 'document_id': 'd1', 'filename': 'midterm-report.pdf',
        'page': 1, 'section': 'Overview', 'content': content,
        'vector': encoder.embed_query(content),
    }
    retriever = SQLiteRetriever(
        database=_FakeDb([row]), embeddings=encoder, embedding_id='test',
        user_id='u', k=3, min_score=0.08,
    )
    docs = retriever.invoke('这份 midterm report 的要求')
    assert docs and docs[0].metadata['filename'] == 'midterm-report.pdf'
