from eval.langsmith_rag import make_examples, score_answer, score_citation, score_retrieval


def test_examples_keep_search_and_answer_references_separate():
    examples = make_examples({"cases": [{
        "id": "q1", "kind": "in_scope", "question": "Why?",
        "must_retrieve_any": ["source fact"], "must_answer_any": ["answer fact"],
    }]})
    assert examples[0]["reference_outputs"]["retrieval_cues"] == ["source fact"]
    assert examples[0]["reference_outputs"]["answer_cues"] == ["answer fact"]


def test_retrieval_and_answer_are_scored_independently():
    ref = {"kind": "in_scope", "retrieval_cues": ["source fact"], "answer_cues": ["answer fact"]}
    out = {"retrieved": ["source fact"], "answer": "unrelated", "mode": "extractive", "sources": []}
    assert score_retrieval(out, ref)["score"] == 1
    assert score_answer(out, ref)["score"] == 0


def test_off_topic_and_citation():
    out = {"retrieved": ["irrelevant"], "answer": "unsupported [S9]", "mode": "llm", "sources": [{"id": "S1"}]}
    off = {"kind": "off_topic"}
    assert score_retrieval(out, off)["score"] == 0
    assert score_answer(out, off)["score"] == 0
    assert score_citation(out, {"kind": "in_scope"})["score"] == 0
