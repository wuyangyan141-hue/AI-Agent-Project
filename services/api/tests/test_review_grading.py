from app.skills.review_session import begin_review, daily_quiz, evaluate_review, resolve_topic


def test_builtin_topic_grades_by_checklist_without_docs(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: False)
    monkeypatch.setattr('app.skills.review_session._knowledge_topics', lambda limit=6: [])
    monkeypatch.setattr('app.skills.review_session._knowledge_passages', lambda topic, limit=3: [])
    result = evaluate_review(
        'B+树',
        'B+树叶子节点之间有链表，所以适合范围查询。',
    )
    assert result['result'] == 'correct'
    assert result['score'] >= 80
    assert '叶子节点' in result['matched']


def test_with_materials_builtin_topic_is_replaced(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['碳酸锂', '价格预测', '供需'],
    )
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_passages',
        lambda topic, limit=3: [{
            'snippet': '碳酸锂价格预测依赖供需预期与均衡价格。',
            'filename': '锂研报.pdf',
            'page': 10,
            'score': 0.5,
        }],
    )
    started = begin_review('B+树')
    assert started['topic'] != 'B+树'
    assert '叶子节点' not in (started.get('criteria') or [])
    result = evaluate_review('B+树', '我认为供需和价格预测很重要')
    assert '叶子节点' not in result['criteria']
    assert '叶子节点' not in result['feedback']


def test_daily_quiz_prefers_material_topics(monkeypatch):
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['碳酸锂', '价格预测', '供需'],
    )
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_passages',
        lambda topic, limit=3: [{'snippet': f'{topic} 相关正文', 'filename': '锂.pdf', 'page': 1}],
    )
    quiz = daily_quiz(limit=3)
    assert quiz['count'] == 3
    assert all(item['topic'] not in {'B+树', 'Hash索引', '重点'} for item in quiz['items'])


def test_resolve_vague_topic(monkeypatch):
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['动态优选'],
    )
    assert resolve_topic('重点') == '动态优选'
