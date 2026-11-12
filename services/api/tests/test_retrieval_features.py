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


def test_local_hash_collision_cannot_create_evidence_without_word_overlap():
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
    # Same vector as content → pure cosine soft-hit even with no token overlap.
    class FixedEmb(LocalLexicalEmbeddings):
        def embed_query(self, text: str):
            return list(row['vector']) if text != content else list(row['vector'])

    retriever = SQLiteRetriever(
        database=_FakeDb([row]), embeddings=FixedEmb(), embedding_id='test',
        user_id='u', k=3, min_score=0.10,
    )
    docs = retriever.invoke('完全不同的中文短问')
    assert docs == []


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
