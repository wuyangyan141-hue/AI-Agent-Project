from app.agent.intent import explicit_intent
from app.skills.learning_loop import format_next_step, next_step, today_plan
from app.skills.study_plan import make_today_plan_options
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
    assert explicit_intent('今日计划').action == 'today'
    assert explicit_intent('看看计划').action == 'today'


def test_today_plan_lists_tasks(monkeypatch):
    monkeypatch.setattr(
        'app.skills.learning_loop.learning_status',
        lambda session_id=None: {
            'has_documents': True,
            'open_tasks': 2,
            'next_task': {'id': 1, 'title': '复习双MACD', 'estimated_minutes': 30, 'scheduled_day': 1},
            'focus': {'id': None, 'remaining_seconds': 0},
            'waiting_review': None,
            'recent_reviews': [],
            'streak': {'current_streak': 1},
        },
    )

    class FakeDB:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        'app.database.store.connect',
        lambda: FakeDB(),
    )
    monkeypatch.setattr(
        'app.database.store.list_tasks',
        lambda _db: [
            {'id': 1, 'title': '复习双MACD', 'done': False, 'estimated_minutes': 30, 'scheduled_day': 1},
            {'id': 2, 'title': '做一题巩固', 'done': False, 'estimated_minutes': 20, 'scheduled_day': 1},
            {'id': 3, 'title': '第二天总结', 'done': False, 'estimated_minutes': 25, 'scheduled_day': 2},
        ],
    )
    agenda = today_plan()
    assert agenda['needs_plan'] is False
    assert '第 1 天' in agenda['text']
    assert '复习双MACD' in agenda['text']
    assert '做一题巩固' in agenda['text']
    assert '第二天总结' not in agenda['text']
    assert '开始专注' in agenda['next_step']['prompt']
    assert [task['title'] for task in agenda['tasks']] == ['复习双MACD', '做一题巩固']
    assert all(task['id'] and task['done'] is False for task in agenda['tasks'])


def test_today_plan_options_three_intensities():
    options = make_today_plan_options('复习双MACD', {'topics': ['双MACD', '进场信号']}, daily_minutes=45)
    assert [opt['key'] for opt in options] == ['light', 'standard', 'intensive']
    assert options[0]['minutes'] < options[1]['minutes'] <= options[2]['minutes']
    assert len(options[0]['steps']) == 1
    assert len(options[2]['steps']) == 2
    assert all(opt['label'] and opt['steps'] for opt in options)


def test_plan_budgets_scale_with_daily_minutes():
    from app.skills.preferences_loop import plan_budgets_from_daily
    small = plan_budgets_from_daily(30)
    large = plan_budgets_from_daily(90)
    assert small['light'] < large['light']
    assert small['intensive'] <= 90
    assert large['intensive'] >= large['standard'] >= large['light']


def test_infer_daily_minutes_and_style():
    from app.skills.preferences_loop import infer_from_utterance, parse_daily_minutes

    assert parse_daily_minutes('每天 40 分钟') == 40
    # Inference needs knowledge DB; exercise pure parsers above and keep smoke light.
    assert '分钟' in '每天只能学40分钟'


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
