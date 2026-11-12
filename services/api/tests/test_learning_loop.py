from app.agent.intent import explicit_intent
from app.skills.learning_loop import format_next_step, next_step
from app.skills.review_session import daily_quiz, weak_point_review
from app.knowledge.overview import build_summary, extract_keywords


def test_keywords_prefer_technical_tokens():
    keys = extract_keywords([
        'The midterm report requires a project objective and grading criteria for the team.',
        'Hash index and B+ tree are compared for range queries.',
    ])
    assert any('midterm' in k.lower() or 'project' in k.lower() or 'grading' in k.lower() or 'hash' in k.lower() for k in keys)
    assert len(keys) <= 8


def test_summary_mentions_filename():
    summary = build_summary('guide.pdf', ['objective', 'criteria'], [{'title': 'Overview', 'page': 1}], 4)
    assert 'guide.pdf' in summary and 'objective' in summary


def test_next_step_upload_without_docs(monkeypatch):
    monkeypatch.setattr('app.skills.learning_loop.learning_status', lambda: {
        'has_documents': False, 'open_tasks': 0, 'next_task': None,
        'focus': {'id': None, 'remaining_seconds': 0}, 'waiting_review': None,
        'recent_reviews': [], 'streak': {'current_streak': 0},
    })
    step = next_step()
    assert step['action'] == 'upload'
    assert '上传' in format_next_step(step)


def test_daily_quiz_and_weak_point():
    quiz = daily_quiz(limit=2)
    assert quiz['count'] == 2 and quiz['items'][0]['question']
    weak = weak_point_review([{'topic': 'Hash索引', 'status': 'needs_review'}])
    assert weak['topic'] == 'Hash索引'


def test_focus_and_next_intents():
    assert explicit_intent('下一步').action == 'next'
    assert explicit_intent('怎么办').action == 'next'
    assert explicit_intent('卡住了').action == 'next'
    assert explicit_intent('薄弱点回顾').action == 'weak'


def test_demo_agent_coaches_next_step(monkeypatch):
    from app.agent.service import StudyAgent
    from app.database import store

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr('app.skills.learning_loop.learning_status', lambda: {
        'has_documents': False, 'open_tasks': 0, 'next_task': None,
        'focus': {'id': None, 'remaining_seconds': 0}, 'waiting_review': None,
        'recent_reviews': [], 'streak': {'current_streak': 0},
    })
    reply = StudyAgent(store.connect)._demo_coach('你好')
    assert '推断' in reply or '进度' in reply
    assert '上传' in reply
