from app.knowledge.integration import get_knowledge
from app.skills.review_session import _offline_objective


def test_record_exchange_strips_sources_for_plan_modes():
    knowledge = get_knowledge()
    payload = knowledge.record_exchange(
        'local-user',
        '制定计划',
        '计划初稿',
        None,
        {'mode': 'plan_revise', 'sources': [{'id': 'S1', 'snippet': 'fake'}]},
    )
    assert payload.get('mode') == 'plan_revise'
    assert payload.get('sources') == []


def test_offline_multiple_choice_uses_passage_facts():
    passages = [
        {
            'snippet': '二叉搜索树的中序遍历得到升序序列。左子树所有键小于根节点。',
            'filename': 'ds.pdf',
        }
    ]
    question, options, correct_key, reference = _offline_objective(
        '二叉搜索树', ['中序遍历'], 'multiple_choice', passages
    )
    assert len(options) >= 3
    assert correct_key in {o['key'] for o in options}
    correct_text = next(o['text'] for o in options if o['key'] == correct_key)
    assert correct_text == reference or reference in correct_text or correct_text in reference
    assert '干扰项' not in question
    assert not any('干扰项' in (o.get('text') or '') for o in options)