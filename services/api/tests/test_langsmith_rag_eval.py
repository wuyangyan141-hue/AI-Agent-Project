from eval.langsmith_rag import (
    make_examples, score_answer, score_answer_all, score_answer_clean,
    score_citation, score_mode, score_retrieval, score_retrieval_all,
)


def test_examples_keep_search_and_answer_references_separate():
    examples = make_examples({"cases": [{
        "id": "q1", "kind": "in_scope", "question": "Why?",
        "must_retrieve_any": ["source fact"], "must_answer_any": ["answer fact"],
        "must_retrieve_all": ["source fact"], "must_answer_all": ["answer fact"],
        "must_not_answer_any": ["leak"],
    }]})
    ref = examples[0]["reference_outputs"]
    assert ref["retrieval_cues"] == ["source fact"]
    assert ref["answer_cues"] == ["answer fact"]
    assert ref["retrieval_all_cues"] == ["source fact"]
    assert ref["answer_all_cues"] == ["answer fact"]
    assert ref["answer_forbid_cues"] == ["leak"]


def test_retrieval_and_answer_are_scored_independently():
    ref = {
        "kind": "in_scope",
        "retrieval_cues": ["source fact"],
        "retrieval_all_cues": [],
        "retrieval_forbid_cues": [],
        "answer_cues": ["answer fact"],
        "answer_all_cues": [],
        "answer_forbid_cues": [],
    }
    out = {"retrieved": ["source fact"], "answer": "unrelated", "mode": "extractive", "sources": []}
    assert score_retrieval(out, ref)["score"] == 1
    assert score_answer(out, ref)["score"] == 0


def test_answer_all_groups_scored():
    ref = {
        "kind": "in_scope",
        "answer_cues": ["交叉", "变异"],
        "answer_all_groups": [["crossover", "交叉"], ["mutation", "变异"]],
        "answer_all_cues": [],
        "answer_forbid_cues": [],
        "expect_mode": ["llm"],
        "forbid_modes": [],
    }
    zh = {"retrieved": [], "answer": "遗传算法使用交叉与变异。", "mode": "llm", "sources": [{"id": "S1"}]}
    assert score_answer_all(zh, ref)["score"] == 1
    assert score_answer(zh, ref)["score"] == 1


def test_richer_all_and_clean_checks():
    ref = {
        "kind": "in_scope",
        "retrieval_cues": ["A*", "g(n)"],
        "retrieval_all_cues": ["g(n)", "h(n)"],
        "retrieval_forbid_cues": [],
        "answer_cues": ["g(n)", "h(n)"],
        "answer_all_cues": ["g(n)", "h(n)"],
        "answer_forbid_cues": ["Mars"],
        "expect_mode": ["extractive", "llm"],
        "forbid_modes": [],
    }
    good = {
        "retrieved": ["A* uses g(n) and h(n)"],
        "answer": "f(n)=g(n)+h(n)",
        "mode": "extractive",
        "sources": [],
    }
    assert score_retrieval(good, ref)["score"] == 1
    assert score_retrieval_all(good, ref)["score"] == 1
    assert score_answer(good, ref)["score"] == 1
    assert score_answer_all(good, ref)["score"] == 1
    assert score_answer_clean(good, ref)["score"] == 1
    assert score_mode(good, ref)["score"] == 1

    leak = {**good, "answer": "g(n) and h(n) plus Mars"}
    assert score_answer_clean(leak, ref)["score"] == 0
    assert score_answer(leak, ref)["score"] == 0


def test_off_topic_and_citation():
    out = {"retrieved": ["irrelevant"], "answer": "unsupported [S9]", "mode": "llm", "sources": [{"id": "S1"}]}
    off = {"kind": "off_topic", "expect_mode": ["no_evidence"], "forbid_modes": ["llm"], "answer_forbid_cues": []}
    assert score_retrieval(out, off)["score"] == 0
    assert score_answer(out, off)["score"] == 0
    assert score_mode(out, off)["score"] == 0
    assert score_citation(out, {"kind": "in_scope"})["score"] == 0
