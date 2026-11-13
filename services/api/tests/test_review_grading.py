from app.skills.review_session import begin_review, daily_quiz, evaluate_review, public_review, resolve_topic


def test_offline_multiple_choice_hides_key_and_grades(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['碳酸锂', '价格预测', '供需', '库存'],
    )
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_passages',
        lambda topic, limit=3: [{'snippet': f'{topic} 相关正文', 'filename': '锂.pdf', 'page': 1}],
    )
    started = begin_review('碳酸锂', preferred_type='multiple_choice')
    assert started['question_type'] == 'multiple_choice'
    assert started['correct_key'] == 'A'
    assert len(started['options']) == 4
    public = public_review(started)
    assert 'correct_key' not in public and public['options']
    ok = evaluate_review('碳酸锂', 'A', snapshot=started)
    assert ok['result'] == 'correct' and ok['score'] == 100
    bad = evaluate_review('碳酸锂', 'B', snapshot=started)
    assert bad['result'] == 'needs_review' and bad['score'] == 0


def test_give_up_reveals_reference_answer():
    snapshot = {
        'topic': '双MACD',
        'question_type': 'short_answer',
        'options': [],
        'correct_key': '',
        'criteria': ['金叉进场', '死叉离场'],
        'sources': [],
        'grading_mode': 'offline',
        'reference_answer': '两类基本进场信号是金叉与死叉确认。',
    }
    result = evaluate_review('双MACD', '不知道', snapshot=snapshot)
    assert result['result'] == 'needs_review'
    assert '解析：' in result['feedback'] or '参考' in result['feedback']
    assert '金叉' in result['feedback']
    assert result['feedback'].count('金叉与死叉确认') == 1


def test_ask_answer_on_multiple_choice_reveals_key():
    snapshot = {
        'topic': '双MACD',
        'question_type': 'multiple_choice',
        'options': [
            {'key': 'A', 'text': '替代日线结构'},
            {'key': 'B', 'text': '震荡与能量对比'},
            {'key': 'C', 'text': '全自动交易'},
            {'key': 'D', 'text': '只看微观K线'},
        ],
        'correct_key': 'B',
        'criteria': ['能量'],
        'sources': [{'filename': '双MACD指标交易攻略.pdf', 'page': 12, 'snippet': '柱状图能量'}],
        'grading_mode': 'offline',
        'reference_answer': '13、21 柱与 55、89 叠比，用来看能量强弱。',
    }
    result = evaluate_review('双MACD', '答案是什么', snapshot=snapshot)
    assert result['result'] == 'needs_review'
    assert '【正确选项：B】' in result['feedback']
    assert '震荡与能量对比' in result['feedback']
    assert result['feedback'].count('13、21 柱与 55、89 叠比') == 1
    assert '《双MACD指标交易攻略.pdf》第12页' in result['feedback']


def test_wrong_option_explains_choice_and_does_not_duplicate_reference():
    snapshot = {
        'topic': '双MACD',
        'question_type': 'multiple_choice',
        'options': [
            {'key': 'A', 'text': '替代日线结构'},
            {'key': 'B', 'text': '震荡与能量对比'},
            {'key': 'C', 'text': '全自动交易'},
            {'key': 'D', 'text': '只看微观K线'},
        ],
        'correct_key': 'B',
        'criteria': ['能量'],
        'sources': [{'filename': '双MACD指标交易攻略.pdf', 'page': 8}],
        'grading_mode': 'model',
        'reference_answer': '参考答案：13、21MACD柱状图用于能量对比。',
    }
    result = evaluate_review('双MACD', 'A', snapshot=snapshot)
    assert result['result'] == 'needs_review'
    assert '你选的是 A' in result['feedback']
    assert '【正确选项：B】' in result['feedback']
    assert result['feedback'].count('13、21MACD柱状图用于能量对比') == 1
    assert '参考答案：参考答案' not in result['feedback']
    assert '可在 《双MACD指标交易攻略.pdf》第8页' in result['feedback']


def test_infers_correct_option_when_key_missing_but_options_exist():
    snapshot = {
        'topic': '双MACD',
        'question_type': 'short_answer',
        'options': [
            {'key': 'A', 'text': '替代日线以上级别的结构与定势分析'},
            {'key': 'B', 'text': '作为震荡与能量指标，通过与55、89MACD等比例面积叠加'},
            {'key': 'C', 'text': '完全取代裸K线分型划线'},
            {'key': 'D', 'text': '仅用于识别微观K线止跌止涨形态'},
        ],
        'correct_key': '',
        'criteria': ['能量'],
        'sources': [{'filename': '双MACD指标交易攻略.pdf', 'page': 1}],
        'grading_mode': 'model',
        'reference_answer': '13、21MACD的柱状图功能类似于一个震荡、能量指标，通过与55、89MACD等比例面积叠加后的面积对比。',
    }
    result = evaluate_review('双MACD', 'A', snapshot=snapshot)
    assert '【正确选项：B】' in result['feedback']
    assert result['result'] == 'needs_review'


def test_display_question_does_not_embed_objective_options():
    from app.skills.review_session import _display_question
    text = _display_question(
        '双MACD柱状图的核心功能是什么？',
        [
            {'key': 'A', 'text': '替代日线结构'},
            {'key': 'B', 'text': '震荡与能量对比'},
        ],
        'multiple_choice',
    )
    assert 'A. 替代日线结构' not in text
    assert '【单选】' in text


def test_true_false_accepts_chinese_labels(monkeypatch):
    snapshot = {
        'topic': '供需',
        'question_type': 'true_false',
        'options': [{'key': 'A', 'text': '正确'}, {'key': 'B', 'text': '错误'}],
        'correct_key': 'A',
        'criteria': ['供需影响价格'],
        'sources': [],
        'grading_mode': 'offline',
        'reference_answer': '资料支持该判断。',
    }
    assert evaluate_review('供需', '正确', snapshot=snapshot)['result'] == 'correct'
    assert evaluate_review('供需', '错误', snapshot=snapshot)['result'] == 'needs_review'


def test_builtin_topic_grades_by_checklist_without_docs(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: False)
    monkeypatch.setattr('app.skills.review_session._knowledge_topics', lambda limit=6: [])
    monkeypatch.setattr('app.skills.review_session._knowledge_passages', lambda topic, limit=3: [])
    result = evaluate_review(
        'B+树',
        'B+树叶子节点之间有链表，所以适合范围查询。',
    )
    assert result['result'] == 'correct'
    assert result['score'] >= 80
    assert '叶子节点' in result['matched']


def test_with_materials_builtin_topic_is_replaced(monkeypatch):
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['碳酸锂', '价格预测', '供需'],
    )
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_passages',
        lambda topic, limit=3: [{
            'snippet': '碳酸锂价格预测依赖供需预期与均衡价格。',
            'filename': '锂研报.pdf',
            'page': 10,
            'score': 0.5,
        }],
    )
    started = begin_review('B+树')
    assert started['topic'] != 'B+树'
    assert '叶子节点' not in (started.get('criteria') or [])
    result = evaluate_review('B+树', '我认为供需和价格预测很重要')
    assert '叶子节点' not in result['criteria']
    assert '叶子节点' not in result['feedback']


def test_daily_quiz_prefers_material_topics(monkeypatch):
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['碳酸锂', '价格预测', '供需'],
    )
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_passages',
        lambda topic, limit=3: [{'snippet': f'{topic} 相关正文', 'filename': '锂.pdf', 'page': 1}],
    )
    quiz = daily_quiz(limit=3)
    assert quiz['count'] == 3
    assert all(item['topic'] not in {'B+树', 'Hash索引', '重点'} for item in quiz['items'])


def test_resolve_vague_topic(monkeypatch):
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['动态优选'],
    )
    assert resolve_topic('重点') == '动态优选'
    assert resolve_topic('预测') == '动态优选'


def test_begin_review_resolves_vague_topic_even_with_document_ids(monkeypatch):
    """Desktop pet often sends document_ids; vague「今日重点」must still resolve."""
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['双MACD进场信号', '金叉确认'],
    )
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_passages',
        lambda topic, limit=3: [{
            'id': 's1',
            'snippet': f'{topic} 金叉确认后进场，死叉离场。',
            'filename': 'macd.pdf',
            'page': 2,
            'score': 0.8,
        }],
    )

    class FakeKnowledge:
        chat_model = None

        def search(self, *_args, **_kwargs):
            return [{
                'id': 's1',
                'snippet': '双MACD进场信号 金叉确认后进场，死叉离场。',
                'filename': 'macd.pdf',
                'page': 2,
                'score': 0.8,
            }]

        def summarize_document(self, *_args, **_kwargs):
            return {'sources': []}

    monkeypatch.setattr(
        'app.knowledge.integration.get_knowledge',
        lambda: FakeKnowledge(),
    )
    started = begin_review('今日重点', document_ids=['doc-1'], preferred_type='short_answer')
    assert started['topic'] == '双MACD进场信号'
    assert started['grading_mode'] == 'offline'
    assert '复习题未提供有效原文依据' not in (started.get('question') or '')


def test_begin_review_falls_back_when_model_quotes_invalid(monkeypatch):
    monkeypatch.setattr(
        'app.skills.review_session._knowledge_topics',
        lambda limit=6: ['金叉确认'],
    )
    monkeypatch.setattr('app.skills.review_session._has_ready_documents', lambda: True)

    class BadQuoteModel:
        def invoke(self, *_args, **_kwargs):
            raise AssertionError('structured should be mocked')

    class FakeKnowledge:
        chat_model = BadQuoteModel()

        def search(self, *_args, **_kwargs):
            return [{
                'id': 's1',
                'snippet': '金叉确认后进场，死叉离场。',
                'filename': 'macd.pdf',
                'page': 2,
                'score': 0.8,
            }]

        def summarize_document(self, *_args, **_kwargs):
            return {'sources': []}

    class FakeReview:
        topic = '金叉确认'
        question_type = 'short_answer'
        question = '请说明金叉确认的含义或作用，并举一个例子。'
        options = []
        correct_key = ''
        reference_answer = '模型编造的参考答案不够贴原文。'
        criteria = ['金叉确认']
        source_ids = ['s1']
        quotes = ['这段话并不在原文里出现过的内容']

    monkeypatch.setattr('app.knowledge.integration.get_knowledge', lambda: FakeKnowledge())
    monkeypatch.setattr(
        'app.knowledge.grounding.structured',
        lambda *_args, **_kwargs: FakeReview(),
    )
    started = begin_review('金叉确认', document_ids=['doc-1'], preferred_type='short_answer')
    assert started['grading_mode'] == 'offline'
    assert started['question']
    assert '未提供有效原文依据' not in started['question']


def test_generic_keyword_ranked_below_specific_title():
    from app.skills.review_session import _topic_rank
    assert _topic_rank('双MACD进场信号') > _topic_rank('预测')
    assert _topic_rank('金叉') > _topic_rank('分析')
