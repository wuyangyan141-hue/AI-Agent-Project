from app.agent.intent import explicit_intent
from app.skills.learning_loop import format_next_step, next_step


def test_answer_echo_is_not_new_review():
    assert explicit_intent('我来回答复习题：重点').action == 'chat'
    assert explicit_intent('开始复习 B+树').action == 'review'
    assert explicit_intent('我想小测').action == 'quiz'
    assert explicit_intent('小测一下').action == 'quiz'


def test_review_answer_prompt_does_not_loop(monkeypatch):
    monkeypatch.setattr('app.skills.learning_loop.learning_status', lambda: {
        'has_documents': True, 'open_tasks': 0, 'next_task': None,
        'focus': {'id': None, 'remaining_seconds': 0},
        'waiting_review': {'id': 1, 'topic': '重点', 'status': 'waiting'},
        'recent_reviews': [], 'streak': {'current_streak': 0},
    })
    step = next_step('review')
    assert step['action'] == 'review_answer'
    assert step['prompt'] == ''
    assert '重点' in (step.get('placeholder') or '')
    text = format_next_step(step)
    assert '我来回答复习题' not in text
