from app.skills.question_banks.chapter2 import (
    chapter2_match_item,
    chapter2_quiz_items,
    looks_like_chapter2,
)
from app.skills.review_session import begin_review, daily_quiz


def test_looks_like_chapter2_filename():
    assert looks_like_chapter2('DSAI5205_Chapter2_2026.pdf')
    assert looks_like_chapter2('chapter2-search.pdf')
    assert not looks_like_chapter2('双MACD指标交易攻略.pdf')


def test_chapter2_options_are_knowledge_points():
    item = chapter2_match_item('BFS')
    assert item is not None
    assert item['question_type'] == 'multiple_choice'
    assert 3 <= len(item['options']) <= 4
    correct = next(row['text'] for row in item['options'] if row['key'] == item['correct_key'])
    assert '内存' in correct or 'unexpanded' in correct.lower() or '节点' in correct
    blob = ' '.join(row['text'] for row in item['options'])
    assert 'Chapter' not in blob
    assert 'DSAI5205' not in blob
    assert '干扰项' not in blob


def test_chapter2_quiz_covers_distinct_topics():
    items = chapter2_quiz_items(3, salt='unit')
    assert len(items) == 3
    topics = {item['topic'] for item in items}
    assert len(topics) == 3


def test_begin_review_uses_chapter2_bank(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_chapter2_materials', lambda document_ids=None: True)
    monkeypatch.setattr(
        'app.skills.review_session._passages_about_topic',
        lambda topic, document_ids=None, k=4: [{
            'snippet': f'{topic}: breadth-first search remembers unexpanded nodes at a level.',
            'filename': 'DSAI5205_Chapter2_2026.pdf',
            'page': 21,
        }],
    )
    monkeypatch.setattr(
        'app.skills.review_session.resolve_topic',
        lambda topic: 'BFS' if topic in {'今日重点', '重点', 'BFS'} else topic,
    )
    started = begin_review('BFS', preferred_type='multiple_choice')
    assert started['grading_mode'] == 'curated'
    assert started['bank'] == 'chapter2'
    assert started['topic'] == 'BFS'
    assert all('干扰项' not in (opt.get('text') or '') for opt in started['options'])


def test_daily_quiz_prefers_chapter2_bank(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_chapter2_materials', lambda document_ids=None: True)
    monkeypatch.setattr(
        'app.skills.review_session._passages_about_topic',
        lambda topic, document_ids=None, k=4: [{
            'snippet': f'Lecture note about {topic}',
            'filename': 'DSAI5205_Chapter2_2026.pdf',
            'page': 2,
        }],
    )
    quiz = daily_quiz(limit=3)
    assert quiz.get('bank') == 'chapter2'
    assert quiz['count'] == 3
    assert {item['grading_mode'] for item in quiz['items']} == {'curated'}
    assert len({item['topic'] for item in quiz['items']}) == 3
