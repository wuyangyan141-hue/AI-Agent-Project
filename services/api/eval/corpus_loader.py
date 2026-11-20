"""Upload eval corpora (single or multi-document) into a temporary KnowledgeService DB."""
from __future__ import annotations

from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent


def corpus_catalog(gold: dict) -> dict[str, Path]:
    """Map logical doc id -> absolute path under eval/."""
    entries = gold.get('corpus_files')
    if entries:
        catalog: dict[str, Path] = {}
        for item in entries:
            doc_id = item['id']
            rel = item['path']
            catalog[doc_id] = (EVAL_DIR / rel).resolve()
        return catalog
    rel = gold.get('corpus_file') or 'corpus/search_basics.txt'
    return {'default': (EVAL_DIR / rel).resolve()}


def missing_corpus_paths(gold: dict) -> list[Path]:
    return [path for path in corpus_catalog(gold).values() if not path.is_file()]


def upload_corpora(kb, gold: dict, user: str) -> dict[str, str]:
    """Return logical id -> knowledge document id."""
    mapping: dict[str, str] = {}
    for doc_id, path in corpus_catalog(gold).items():
        if not path.is_file():
            raise FileNotFoundError(f'Eval corpus missing: {path}')
        uploaded = kb.upload(user, path.name, path.read_bytes())
        if uploaded.get('status') == 'error':
            raise RuntimeError(uploaded.get('error') or f'upload failed: {path.name}')
        mapping[doc_id] = uploaded['id']
    return mapping


def case_document_ids(case: dict, gold: dict, mapping: dict[str, str]) -> list[str]:
    keys = case.get('documents')
    if keys:
        return [mapping[k] for k in keys]
    default = gold.get('default_documents')
    if default:
        return [mapping[k] for k in default]
    if 'default' in mapping:
        return [mapping['default']]
    return list(mapping.values())