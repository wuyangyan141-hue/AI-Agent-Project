"""Guided review: prefer uploaded materials; built-ins only when knowledge base is empty."""
from __future__ import annotations

import re

QUESTIONS = {
    'B+树': ('B+ 树为什么适合范围查询？', ('叶子节点', '链表', '范围查询')),
    'Hash索引': ('Hash 索引为什么通常不适合范围查询？', ('无序', '哈希', '范围查询')),
}

_VAGUE = {'重点', '今日重点', '知识点', '核心概念', '今日', '复习', '核心', '内容'}
_BUILTIN_TOPICS = set(QUESTIONS)


def _is_good_term(word: str) -> bool:
    token = (word or '').strip()
    if not token or token in _VAGUE or token in _BUILTIN_TOPICS:
        return False
    if re.fullmatch(r'\d+', token):
        return False
    if re.search(r'[a-zA-Z]', token):
        return len(token) >= 3
    return len(token) >= 2 and not re.fullmatch(r'[\u3400-\u9fff]', token)


def _has_ready_documents() -> bool:
    try:
        from ..knowledge.integration import get_knowledge

        return any(
            doc.get('status') == 'ready' and not doc.get('needs_reindex')
            for doc in get_knowledge().list_documents('local-user')
        )
    except Exception:
        return False


def _knowledge_topics(limit: int = 6) -> list[str]:
    """Concrete study topics from document keywords / outline titles."""
    try:
        from ..knowledge.integration import get_knowledge

        knowledge = get_knowledge()
        docs = [
            doc for doc in knowledge.list_documents('local-user')
            if doc.get('status') == 'ready' and not doc.get('needs_reindex')
        ]
        topics: list[str] = []
        for doc in docs[:4]:
            overview = knowledge.document_overview('local-user', doc['id'])
            for word in overview.get('keywords') or []:
                if _is_good_term(word) and word not in topics:
                    topics.append(word)
            for item in overview.get('outline') or []:
                title = re.sub(r'\s+', ' ', (item.get('title') or '')).strip()
                title = re.sub(r'^第\s*\d+\s*页$', '', title).strip()
                if _is_good_term(title) and 2 <= len(title) <= 40 and title not in topics:
                    topics.append(title)
            if len(topics) >= limit:
                break
        return topics[:limit]
    except Exception:
        return []


def _topic_supported_by_materials(topic: str, passages: list[dict] | None = None) -> bool:
    """True if topic looks like it belongs to the uploaded corpus."""
    if topic in _BUILTIN_TOPICS:
        blob = ' '.join((p.get('snippet') or '') + ' ' + (p.get('filename') or '') for p in (passages or []))
        # Builtin CS topics must actually appear in retrieved text; otherwise reject.
        markers = [topic, *QUESTIONS.get(topic, ('', ()))[1]]
        return any(marker and marker.lower() in blob.lower() for marker in markers)
    return True


def _knowledge_passages(topic: str, limit: int = 3) -> list[dict]:
    try:
        from ..knowledge.integration import get_knowledge

        query = topic if _is_good_term(topic) or topic in _BUILTIN_TOPICS else ' '.join(_knowledge_topics(4))
        if not query.strip():
            return []
        return get_knowledge().search('local-user', query, None, k=limit)
    except Exception:
        return []


def _material_criteria(topic: str, passages: list[dict] | None = None) -> list[str]:
    criteria: list[str] = []
    if _is_good_term(topic) and topic not in _BUILTIN_TOPICS:
        criteria.append(topic)
    texts = [p.get('snippet') or '' for p in (passages or [])]
    if not texts:
        try:
            from ..knowledge.integration import get_knowledge

            knowledge = get_knowledge()
            for doc in knowledge.list_documents('local-user')[:2]:
                if doc.get('status') != 'ready' or doc.get('needs_reindex'):
                    continue
                overview = knowledge.document_overview('local-user', doc['id'])
                texts.extend(overview.get('keywords') or [])
                texts.extend(item.get('preview') or '' for item in (overview.get('outline') or [])[:4])
        except Exception:
            pass
    from ..knowledge.overview import extract_keywords

    for word in extract_keywords([t for t in texts if t], limit=12):
        if word in _BUILTIN_TOPICS:
            continue
        if _is_good_term(word) and word not in criteria and word.lower() not in {c.lower() for c in criteria}:
            if re.search(r'[a-zA-Z]', word) or len(word) >= 3:
                criteria.append(word)
        if len(criteria) >= 4:
            break
    return criteria[:4]


def _criteria_for_topic(topic: str, passages: list[dict] | None = None) -> list[str]:
    # Uploaded materials always win: never inject B+/Hash checklist onto unrelated PDFs.
    if _has_ready_documents():
        if topic in _BUILTIN_TOPICS and not _topic_supported_by_materials(topic, passages):
            return _material_criteria(resolve_topic('今日重点'), passages)
        return _material_criteria(topic, passages)
    if topic in QUESTIONS:
        return list(QUESTIONS[topic][1])
    return _material_criteria(topic, passages)


def resolve_topic(topic: str) -> str:
    topic = (topic or '').strip() or '今日重点'
    material = _knowledge_topics(8)
    if material:
        # With a knowledge base, ignore vague / leftover builtin CS topics.
        if topic in _VAGUE or topic in _BUILTIN_TOPICS:
            return material[0]
        if any(topic == item or topic in item or item in topic for item in material):
            return topic
        # Unknown free-form topic: still keep it if passages will support it; else first material topic.
        passages = _knowledge_passages(topic, limit=2)
        if passages and _topic_supported_by_materials(topic, passages):
            return topic
        return material[0]
    if topic in QUESTIONS:
        return topic
    if topic not in _VAGUE and _is_good_term(topic):
        return topic
    return list(QUESTIONS.keys())[0] if QUESTIONS else topic


def begin_review(topic: str) -> dict:
    topic = resolve_topic(topic)
    passages = _knowledge_passages(topic, limit=3)
    if topic in _BUILTIN_TOPICS and _has_ready_documents() and not _topic_supported_by_materials(topic, passages):
        topic = resolve_topic('今日重点')
        passages = _knowledge_passages(topic, limit=3)
    criteria = _criteria_for_topic(topic, passages)
    if topic in QUESTIONS and not _has_ready_documents():
        question = QUESTIONS[topic][0]
    else:
        hint = '、'.join(criteria[:3])
        if hint:
            question = (
                f'结合已上传资料，说明「{topic}」的含义或作用，并举一个例子。'
                f'作答时尽量覆盖这些要点：{hint}。'
            )
        else:
            question = f'结合已上传资料，用自己的话解释「{topic}」，并举一个例子。'
    return {'topic': topic, 'question': question, 'criteria': criteria}


def _normalize_hits(answer: str, keywords: list[str]) -> list[str]:
    lower = answer.lower()
    hits = []
    for word in keywords:
        token = word.strip()
        if not token:
            continue
        if token.lower() in lower or token in answer:
            hits.append(token)
            continue
        if not re.search(r'[a-zA-Z0-9]', token) and 2 <= len(token) <= 6:
            if all(ch in answer for ch in token):
                hits.append(token)
    return hits


def evaluate_review(topic: str, answer: str) -> dict:
    """Score by checklist coverage of material key points — not bag-of-words frequency."""
    if not answer.strip():
        raise ValueError('Answer is required')
    topic = resolve_topic(topic)
    passages = _knowledge_passages(topic, limit=3)
    if topic in _BUILTIN_TOPICS and _has_ready_documents() and not _topic_supported_by_materials(topic, passages):
        topic = resolve_topic('今日重点')
        passages = _knowledge_passages(topic, limit=3)
    keywords = _criteria_for_topic(topic, passages)
    # Drop evidence that is unrelated to the checklist (prevents lithium PDF + B+ keywords).
    if keywords and passages:
        filtered = []
        for passage in passages:
            blob = ((passage.get('snippet') or '') + ' ' + (passage.get('filename') or '')).lower()
            if any(word.lower() in blob for word in keywords) or topic.lower() in blob:
                filtered.append(passage)
        passages = filtered or passages[:1]

    hits = _normalize_hits(answer, keywords)
    missing = [word for word in keywords if word not in hits]

    method = '按资料评分要点覆盖打分（提到要点即可，不是词频）'
    if keywords:
        ratio = len(hits) / max(1, len(keywords))
        if ratio >= 0.75:
            result, score, verdict = 'correct', round(70 + 30 * ratio), '基本正确'
            tip = f'覆盖要点：{"、".join(hits)}。'
        elif ratio >= 0.4:
            result, score, verdict = 'partial', round(45 + 35 * ratio), '部分正确'
            tip = f'已覆盖：{"、".join(hits) or "较少"}。未提到：{"、".join(missing)}。'
        else:
            result, score, verdict = 'needs_review', max(10, round(40 * ratio)), '建议重看资料'
            tip = f'要点覆盖不足。请尽量提到：{"、".join(keywords)}。'
    else:
        result, score, verdict = 'needs_review', 0, '暂无评分要点'
        tip = '知识库里还抽不出稳定考点。请确认资料已索引，或换一个资料里的关键词主题。'
        method = '暂无可用评分要点'

    evidence_lines = []
    for index, passage in enumerate(passages[:2], start=1):
        snippet = re.sub(r'\s+', ' ', passage.get('snippet') or '').strip()[:110]
        name = passage.get('filename') or '资料'
        page = passage.get('page')
        loc = f'第 {page} 页' if page else '正文'
        if snippet:
            evidence_lines.append(f'[{index}] 《{name}》{loc}：{snippet}')

    feedback = f'{verdict}（{score} 分）。评分方式：{method}。{tip}'
    if keywords:
        feedback += f'\n评分要点：{"、".join(keywords)}'
    if evidence_lines:
        feedback += '\n对照资料：\n' + '\n'.join(evidence_lines)

    return {
        'result': result,
        'score': score,
        'verdict': verdict,
        'feedback': feedback,
        'matched': hits,
        'missing': missing,
        'criteria': keywords,
        'method': method,
        'topic': topic,
        'sources': [
            {
                'filename': p.get('filename'),
                'page': p.get('page'),
                'snippet': (p.get('snippet') or '')[:160],
                'score': p.get('score'),
            }
            for p in passages
        ],
    }


def repair_vague_waiting_reviews() -> None:
    """Rewrite stuck waiting rows (vague or leftover builtin CS topics) using materials."""
    try:
        from ..database import store

        material = _knowledge_topics(6)
        with store.connect() as db:
            rows = db.execute(
                "SELECT id, topic FROM review_sessions WHERE status='waiting' ORDER BY id DESC LIMIT 20"
            ).fetchall()
            for row in rows:
                topic = (row['topic'] or '').strip()
                needs = topic in _VAGUE or (material and topic in _BUILTIN_TOPICS)
                if not needs and _is_good_term(topic):
                    continue
                started = begin_review(topic if topic not in _BUILTIN_TOPICS else '今日重点')
                db.execute(
                    'UPDATE review_sessions SET topic=?, question=? WHERE id=? AND status=?',
                    (started['topic'], started['question'], row['id'], 'waiting'),
                )
            db.commit()
    except Exception:
        return


def daily_quiz(topics: list[str] | None = None, limit: int = 3) -> dict:
    limit = max(1, min(limit, 5))
    material = _knowledge_topics(limit)
    if topics:
        chosen = [resolve_topic(t) for t in topics if t and t.strip()][:limit]
    elif material:
        chosen = material[:limit]
    else:
        chosen = list(QUESTIONS.keys())[:limit]
    if not chosen:
        chosen = ['今日重点']
    items = []
    for topic in chosen:
        started = begin_review(topic)
        items.append({
            'topic': started['topic'],
            'question': started['question'],
            'criteria': started.get('criteria') or [],
        })
    return {
        'kind': 'daily_quiz',
        'count': len(items),
        'items': items,
        'instruction': '逐题作答；有知识库时只按资料考点给分，不会用无关的内置题库。',
    }


def weak_point_review(history: list[dict] | None = None) -> dict:
    material = _knowledge_topics(4)
    weak: list[str] = []
    for row in history or []:
        status = (row.get('status') or row.get('result') or '').lower()
        topic = (row.get('topic') or '').strip()
        if not topic or topic in _VAGUE:
            continue
        if material and topic in _BUILTIN_TOPICS:
            continue
        if status in {'needs_review', 'partial'} and topic not in weak:
            weak.append(topic)
    if not weak:
        weak = material[:2] or list(QUESTIONS.keys())[:2] or ['核心概念']
    topic = resolve_topic(weak[0])
    started = begin_review(topic)
    return {
        'kind': 'weak_point',
        'topic': started['topic'],
        'question': started['question'],
        'weak_topics': weak[:5],
        'hint': '这是根据近期薄弱点/资料关键词挑出的回顾题。',
        'criteria': started.get('criteria') or [],
    }
