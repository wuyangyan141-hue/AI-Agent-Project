"""Small guided review workflow; grading is deliberately transparent."""

QUESTIONS = {
    'B+树': ('B+ 树为什么适合范围查询？', ('叶子', '链')),
    'Hash索引': ('Hash 索引为什么通常不适合范围查询？', ('顺序', '范围')),
}


def begin_review(topic: str) -> dict:
    topic = topic.strip()
    if not topic:
        raise ValueError('Topic is required')
    question, _ = QUESTIONS.get(topic, (f'请用自己的话解释「{topic}」的核心概念，并举一个例子。', ()))
    return {'topic': topic, 'question': question}


def evaluate_review(topic: str, answer: str) -> dict:
    if not answer.strip():
        raise ValueError('Answer is required')
    keywords = QUESTIONS.get(topic, ('', ()))[1]
    if not keywords:
        return {'result': 'needs_review', 'feedback': '已记录回答；当前题目没有可靠的自动评分依据，请结合课程资料核对。'}
    hits = sum(word in answer for word in keywords)
    result = 'correct' if hits == len(keywords) else 'partial' if hits else 'needs_review'
    return {'result': result, 'feedback': '答到了关键点。' if result == 'correct' else '可以进一步考虑关键词：' + '、'.join(keywords) + '。'}


def daily_quiz(topics: list[str] | None = None, limit: int = 3) -> dict:
    """Build a short multi-question quiz from known topics or free-form titles."""
    chosen = [t.strip() for t in (topics or list(QUESTIONS.keys())) if t and t.strip()][: max(1, min(limit, 5))]
    if not chosen:
        chosen = ['今日重点']
    items = []
    for topic in chosen:
        started = begin_review(topic)
        items.append({'topic': started['topic'], 'question': started['question']})
    return {
        'kind': 'daily_quiz',
        'count': len(items),
        'items': items,
        'instruction': '逐题作答即可；答完可以说「下一题」或直接提交答案。',
    }


def weak_point_review(history: list[dict] | None = None) -> dict:
    """Prefer topics previously marked needs_review / partial; otherwise seed defaults."""
    weak: list[str] = []
    for row in history or []:
        status = (row.get('status') or row.get('result') or '').lower()
        topic = (row.get('topic') or '').strip()
        if topic and status in {'needs_review', 'partial'} and topic not in weak:
            weak.append(topic)
    if not weak:
        weak = list(QUESTIONS.keys())[:2] or ['核心概念']
    topic = weak[0]
    started = begin_review(topic)
    return {
        'kind': 'weak_point',
        'topic': started['topic'],
        'question': started['question'],
        'weak_topics': weak[:5],
        'hint': '这是根据近期薄弱点挑出的回顾题。',
    }
