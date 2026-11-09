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
