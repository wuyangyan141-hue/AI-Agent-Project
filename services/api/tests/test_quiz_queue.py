from app.agent.dispatch import resolve_turn
from app.agent.intent import StudyIntent
from app.database import store
from app.skills.review_session import (
    _is_vague_waiting,
    _offline_objective,
    continue_quiz,
    save_quiz_items,
)


def test_next_question_skips_instead_of_grading():
    decision = resolve_turn('下一题', intent=StudyIntent(), route='chat', waiting=True)
    assert decision.kind == 'skip'


def test_short_topic_is_not_treated_as_vague():
    assert _is_vague_waiting('金叉', '【单选题】关于金叉，空格应填哪一项？') is False
    assert _is_vague_waiting('重点', '随便一题') is True


def test_offline_cloze_keeps_the_knowledge_point():
    passages = [{
        'snippet': '碳酸锂价格受库存周期影响，库存下降时价格往往上涨。页眉写着内部培训材料，请勿外传。',
        'filename': '锂.pdf',
    }]
    question, options, correct_key, _reference = _offline_objective(
        '碳酸锂', ['库存周期'], 'multiple_choice', passages,
    )
    correct = next(item['text'] for item in options if item['key'] == correct_key)
    assert '碳酸锂' in question
    assert correct == '碳酸锂'
    assert '请勿外传' not in correct
    assert '干扰项' not in question


def test_quiz_queue_shows_one_waiting_item(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'quiz.db'))
    items = [
        {'topic': '库存周期', 'question': '第一题', 'question_type': 'multiple_choice', 'options': [{'key': 'A', 'text': '甲'}], 'correct_key': 'A'},
        {'topic': '碳酸锂', 'question': '第二题', 'question_type': 'multiple_choice', 'options': [{'key': 'A', 'text': '乙'}], 'correct_key': 'A'},
    ]
    with store.connect() as db:
        saved = save_quiz_items(db, items, 'abc' * 10 + 'abcd')
        waiting = db.execute("SELECT COUNT(*) AS n FROM review_sessions WHERE status='waiting'").fetchone()['n']
        queued = db.execute("SELECT COUNT(*) AS n FROM review_sessions WHERE status='queued'").fetchone()['n']
        db.execute("UPDATE review_sessions SET status='correct' WHERE id=?", (saved[0]['id'],))
        db.commit()
        nxt, summary = continue_quiz(db, saved[0]['session_id'] if 'session_id' in saved[0] else 'abc' * 10 + 'abcd', saved[0]['id'])
    assert waiting == 1 and queued == 1
    assert nxt['topic'] == '碳酸锂'
    assert nxt['status'] == 'waiting'
    assert '第 2/2 题' in nxt['question']
    assert summary == ''
    with store.connect() as db:
        _again, closing = continue_quiz(db, 'abc' * 10 + 'abcd', nxt['id'])
    assert _again is None
    assert '答对 1/2' in closing
