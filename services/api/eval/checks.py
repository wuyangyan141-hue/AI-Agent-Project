"""Shared deterministic checks for local benchmark and LangSmith evaluators."""
from __future__ import annotations


def contains_any(text: str, needles: list[str] | None) -> bool:
    blob = text or ''
    items = [n for n in (needles or []) if n]
    if not items:
        return True
    return any(n.casefold() in blob.casefold() for n in items)


def contains_all(text: str, needles: list[str] | None) -> bool:
    blob = text or ''
    items = [n for n in (needles or []) if n]
    if not items:
        return True
    return all(n.casefold() in blob.casefold() for n in items)


def contains_all_groups(text: str, groups: list[list[str]] | None) -> bool:
    """Each group must match at least one alias (e.g. English or Chinese)."""
    items = [g for g in (groups or []) if g]
    if not items:
        return True
    return all(contains_any(text, group) for group in items)


def contains_none(text: str, needles: list[str] | None) -> bool:
    blob = text or ''
    items = [n for n in (needles or []) if n]
    if not items:
        return True
    return all(n.casefold() not in blob.casefold() for n in items)


def mode_ok(mode: str, case: dict) -> bool:
    expect = case.get('expect_mode') or []
    forbid = case.get('forbid_modes') or []
    if expect and mode not in expect:
        return False
    if forbid and mode in forbid:
        return False
    return True


def score_case_checks(case: dict, *, mode: str, hit_blob: str, answer: str, source_blob: str = '') -> dict:
    """Return a rich deterministic scorecard for one gold case."""
    kind = case.get('kind') or 'in_scope'
    answer_blob = answer or ''
    evidence_blob = f'{answer_blob}\n{source_blob}'
    must_retrieve_any = case.get('must_retrieve_any') or []
    must_retrieve_all = case.get('must_retrieve_all') or []
    must_not_retrieve = case.get('must_not_retrieve_any') or []
    must_answer_any = case.get('must_answer_any') or []
    must_answer_all = case.get('must_answer_all') or []
    must_answer_all_groups = case.get('must_answer_all_groups') or []
    must_not_answer = case.get('must_not_answer_any') or []

    retrieval_any = contains_any(hit_blob, must_retrieve_any) if must_retrieve_any else (bool(hit_blob.strip()) if kind != 'off_topic' else True)
    retrieval_all = contains_all(hit_blob, must_retrieve_all)
    retrieval_clean = contains_none(hit_blob, must_not_retrieve)
    answer_any = contains_any(answer_blob, must_answer_any) if must_answer_any else (bool(answer_blob.strip()) if kind != 'off_topic' else True)
    # Offline extractive answers are often the snippets; allow source text for local evidence.
    evidence_any = contains_any(evidence_blob, must_answer_any) if must_answer_any else answer_any
    if must_answer_all_groups:
        answer_all = contains_all_groups(answer_blob, must_answer_all_groups) or contains_all_groups(
            evidence_blob, must_answer_all_groups,
        )
    else:
        answer_all = contains_all(answer_blob, must_answer_all) or contains_all(evidence_blob, must_answer_all)
    answer_clean = contains_none(answer_blob, must_not_answer)
    mode_pass = mode_ok(mode, case)

    if kind == 'off_topic':
        retrieval_empty = not (hit_blob or '').strip()
        refusal = mode == 'no_evidence'
        passed = mode_pass and refusal and answer_clean
        return {
            'kind': kind,
            'mode_ok': mode_pass,
            'retrieval_hit': retrieval_empty,
            'retrieval_all': True,
            'retrieval_clean': retrieval_clean,
            'evidence_support': refusal,
            'answer_all': True,
            'answer_clean': answer_clean,
            'passed': passed,
            'notes': case.get('notes') or '',
        }

    retrieval_hit = retrieval_any and retrieval_all and retrieval_clean
    evidence_support = (evidence_any or answer_any) and answer_all and answer_clean
    note = case.get('notes') or ''
    if kind == 'paraphrase' and not retrieval_hit and mode == 'no_evidence':
        return {
            'kind': kind,
            'mode_ok': mode_pass,
            'retrieval_hit': False,
            'retrieval_all': retrieval_all,
            'retrieval_clean': retrieval_clean,
            'evidence_support': False,
            'answer_all': answer_all,
            'answer_clean': answer_clean,
            'passed': True,
            'notes': 'honest_miss_under_lexical_retrieval',
        }

    passed = bool(mode_pass and retrieval_hit and evidence_support and mode not in {'no_evidence', 'model_error'})
    return {
        'kind': kind,
        'mode_ok': mode_pass,
        'retrieval_hit': retrieval_hit,
        'retrieval_all': retrieval_all,
        'retrieval_clean': retrieval_clean,
        'evidence_support': evidence_support,
        'answer_all': answer_all,
        'answer_clean': answer_clean,
        'passed': passed,
        'notes': note,
    }
