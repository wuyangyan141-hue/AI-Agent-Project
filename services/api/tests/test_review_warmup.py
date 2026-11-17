from app.skills.review_session import compose_review_message, review_warmup_brief


def test_multiple_choice_option_matches_knowledge_point():
    from app.skills.review_session import _offline_objective

    passages = [{
        'snippet': (
            '碳酸锂价格受库存周期影响，库存下降时价格往往上涨。'
            '页眉写着内部培训材料，请勿外传。'
        ),
        'filename': '锂.pdf',
    }]
    question, options, correct_key, reference = _offline_objective(
        '碳酸锂', ['碳酸锂'], 'multiple_choice', passages,
    )
    correct = next(item['text'] for item in options if item['key'] == correct_key)
    assert '碳酸锂' in question
    assert '碳酸锂' in correct
    assert '请勿外传' not in correct
    assert reference == correct or correct in reference


def test_warmup_lists_the_same_topics_as_the_questions():
    from app.skills.review_session import compose_review_message, warmup_for_reviews

    brief = warmup_for_reviews([
        {'topic': '库存周期'},
        {'topic': '碳酸锂'},
    ])
    text = compose_review_message(brief, '【单选题】根据资料，关于「库存周期」哪一项表述正确？')
    assert '库存周期' in text and '碳酸锂' in text
    assert '页眉' not in text


def test_compose_review_message_joins_brief_and_question():
    text = compose_review_message('【复习要点】\n· A', '【单选题】第一题')
    assert '复习要点' in text and '第一题' in text


def test_review_warmup_without_documents():
    brief = review_warmup_brief('今日重点', None)
    assert brief