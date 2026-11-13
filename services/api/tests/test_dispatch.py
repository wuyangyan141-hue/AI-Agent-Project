from app.agent.dispatch import resolve_turn
from app.agent.entities import normalize_utterance, normalize_zh_numerals
from app.agent.intent import StudyIntent, explicit_intent


def test_normalize_chinese_duration():
    assert '30秒' in normalize_zh_numerals('我要进行三十秒专注')
    assert '25分钟' in normalize_zh_numerals('二十五分钟专注')
    assert normalize_utterance('半分钟专注').startswith('30秒') or '30秒' in normalize_utterance('半分钟专注')


def test_spoken_focus_intent():
    intent = explicit_intent('我需要进行三十秒专注')
    assert intent.action == 'focus'
    assert intent.seconds == 30


def test_priority_command_beats_waiting_answer():
    decision = resolve_turn(
        '我需要进行30s专注',
        intent=explicit_intent('我需要进行30s专注'),
        route='chat',
        waiting=True,
    )
    assert decision.kind == 'command'
    assert decision.intent.action == 'focus'


def test_priority_skip_beats_command_like_answer():
    decision = resolve_turn(
        '先不答',
        intent=StudyIntent(),
        route='chat',
        waiting=True,
    )
    assert decision.kind == 'skip'


def test_waiting_answer_when_plain_chat():
    decision = resolve_turn(
        '预测指对未来价格走势做出判断并举例说明',
        intent=StudyIntent(),
        route='chat',
        waiting=True,
    )
    assert decision.kind == 'review_answer'


def test_give_up_is_graded_not_next_command():
    decision = resolve_turn(
        '不知道',
        intent=StudyIntent(action='next'),
        route='chat',
        waiting=True,
    )
    assert decision.kind == 'review_answer'


def test_ask_for_answer_while_waiting_reveals_key():
    decision = resolve_turn(
        '答案是什么',
        intent=StudyIntent(),
        route='knowledge',
        waiting=True,
    )
    assert decision.kind == 'review_answer'


def test_option_letter_beats_forced_knowledge_while_waiting():
    """Selecting a document sets knowledge=true; 「B」 must still be graded."""
    decision = resolve_turn(
        'B',
        intent=StudyIntent(),
        route='knowledge',
        waiting=True,
    )
    assert decision.kind == 'review_answer'


def test_option_with_text_still_grades_while_waiting():
    decision = resolve_turn(
        'B. 作为震荡与能量指标',
        intent=StudyIntent(),
        route='knowledge',
        waiting=True,
    )
    assert decision.kind == 'review_answer'


def test_soft_next_while_waiting_still_grades_answer():
    decision = resolve_turn(
        '这题我猜是供需预期',
        intent=StudyIntent(action='next'),
        route='chat',
        waiting=True,
    )
    assert decision.kind == 'review_answer'


def test_knowledge_route_not_graded_as_answer():
    decision = resolve_turn(
        '什么是预测？',
        intent=StudyIntent(),
        route='knowledge',
        waiting=True,
    )
    assert decision.kind == 'knowledge'


def test_confused_beats_plan_command():
    decision = resolve_turn(
        '我看不懂',
        intent=StudyIntent(action='plan', goal='复习双MACD', days=3, minutes_per_day=45),
        route='chat',
        waiting=False,
        pending_plan=True,
    )
    assert decision.kind == 'knowledge'
    assert decision.intent.action == 'chat'
    assert decision.route == 'knowledge'


def test_confused_not_swallowed_as_plan_followup_goal():
    decision = resolve_turn(
        '完全看不懂',
        intent=StudyIntent(action='plan', goal='完全看不懂', days=3, minutes_per_day=45),
        route='chat',
        waiting=False,
        pending_plan=True,
    )
    assert decision.kind == 'knowledge'
