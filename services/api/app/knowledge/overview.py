"""Lexical document overview: keywords + outline for offline Chinese UX."""
from __future__ import annotations

import re
from collections import Counter

from .embeddings import features

STOP = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'your', 'are', 'was', 'were', 'will',
    'have', 'has', 'had', 'not', 'but', 'you', 'any', 'all', 'can', 'may', 'into', 'than',
    'then', 'them', 'they', 'their', 'about', 'which', 'when', 'what', 'where', 'while',
    '也', '的', '了', '和', '是', '在', '就', '都', '而', '及', '与', '或', '一个', '我们', '可以',
}


def extract_keywords(texts: list[str], limit: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        for token in features(text):
            if token in STOP or len(token) < 2:
                continue
            if re.fullmatch(r'\d+', token):
                continue
            # Prefer English technical tokens and Chinese 2–3 grams.
            if re.search(r'[a-z]', token) and len(token) < 3:
                continue
            counts[token] += 1
    ranked = [word for word, _ in counts.most_common(40)]
    # Prefer readable surface forms from original casing snippets.
    polished: list[str] = []
    joined = '\n'.join(texts)
    for word in ranked:
        if re.fullmatch(r'[a-z0-9][a-z0-9_-]*', word):
            match = re.search(rf'\b({re.escape(word)})\b', joined, re.I)
            polished.append(match.group(1) if match else word)
        else:
            polished.append(word)
        if len(polished) >= limit:
            break
    return polished


def build_outline(chunks: list[dict], limit: int = 6) -> list[dict]:
    outline = []
    seen = set()
    for chunk in chunks:
        title = (chunk.get('section') or '').strip() or (f"第 {chunk['page']} 页" if chunk.get('page') else '正文')
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        preview = re.sub(r'\s+', ' ', chunk.get('content', '')).strip()[:90]
        outline.append({
            'title': title[:80],
            'page': chunk.get('page'),
            'preview': preview,
            'chunk_id': chunk.get('id'),
        })
        if len(outline) >= limit:
            break
    return outline


def build_summary(filename: str, keywords: list[str], outline: list[dict], chunk_count: int) -> str:
    heads = '、'.join(item['title'] for item in outline[:4]) or '正文片段'
    keys = '、'.join(keywords[:6]) or '（暂无稳定关键词）'
    return (
        f'《{filename}》已建立索引，共 {chunk_count} 个片段。'
        f'主要内容结构包括：{heads}。'
        f'可点关键词：{keys}。'
        '本地演示使用词面检索；问英文资料时优先点关键词，或直接用资料中的术语提问。'
    )
