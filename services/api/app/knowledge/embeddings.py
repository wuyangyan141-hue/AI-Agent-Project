import hashlib
import re

from langchain_core.embeddings import Embeddings
import numpy as np


def features(text: str) -> set[str]:
    """Lexical features only; this is deliberately not advertised as semantic embedding."""
    result = set()
    for token in re.findall(r"[a-z0-9][a-z0-9_-]*", text.lower()):
        if len(token) >= 2 or token.isdigit():
            result.add(token)
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        # 1-grams help short Chinese questions; 2/3-grams keep phrase signal.
        result.update(run)
        for n in (2, 3):
            result.update(run[i:i + n] for i in range(len(run) - n + 1))
    return result


class LocalLexicalEmbeddings(Embeddings):
    """Stable, normalized feature-hash vectors: offline, bilingual, no model fitting."""
    dimension = 2048

    def embed_query(self, text: str) -> list[float]:
        vector = np.zeros(self.dimension, dtype=np.float32)
        for token in features(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest, "little") % self.dimension] += 1
        norm = np.linalg.norm(vector)
        if norm:
            vector /= norm
        return vector.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


def make_embeddings(settings):
    if settings.embedding_provider == "local":
        # Bump id when features()/dimension change so stored vectors reindex.
        return LocalLexicalEmbeddings(), "lexical-hash-v2-2048"
    if settings.embedding_provider != "openai":
        raise ValueError("EMBEDDING_PROVIDER 仅支持 local 或 openai。")
    if not settings.embedding_model:
        raise ValueError("使用语义向量时，请配置 EMBEDDING_MODEL。")
    from langchain_openai import OpenAIEmbeddings

    base_url = settings.embedding_base_url or settings.llm_base_url
    model = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key or settings.llm_api_key or "local-not-required",
        base_url=base_url, max_retries=1, request_timeout=45,
        check_embedding_ctx_length=False, chunk_size=32,
    )
    signature = hashlib.sha256(base_url.encode()).hexdigest()[:12]
    return model, f"openai-compatible:{settings.embedding_model}:{signature}"


def pack_vector(values) -> bytes:
    vector = np.asarray(values, dtype=np.float32)
    if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all():
        raise ValueError("向量模型返回了无效向量。")
    return vector.astype("<f4").tobytes()


def cosine(left, right):
    a = np.asarray(left, dtype=np.float32)
    b = np.frombuffer(right, dtype="<f4") if isinstance(right, bytes) else np.asarray(right, dtype=np.float32)
    if a.shape != b.shape:
        return 0.0
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / norm) if norm else 0.0
