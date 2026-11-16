from app.skills.review_session import compose_review_message, review_warmup_brief


def test_compose_review_message_joins_brief_and_question():
    text = compose_review_message('【复习要点】\n· A', '【单选题】第一题')
    assert '复习要点' in text and '第一题' in text


def test_review_warmup_without_documents():
    brief = review_warmup_brief('今日重点', None)
    assert brief