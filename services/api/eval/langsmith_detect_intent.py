"""LangSmith evaluation for StudyAgent.detect_intent (LLM path only).

Cases are chosen so explicit_intent() returns chat and the classifier is invoked.

Run from services/api (online LLM in Settings or .env):
  python -m eval.langsmith_detect_intent
  python -m eval.langsmith_detect_intent --judge
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import threading
from pathlib import Path

from .corpus_loader import EVAL_DIR

DEFAULT_GOLD = EVAL_DIR / "gold" / "detect_intent_llm.json"
DATASET_PREFIX = "doudou-detect-intent"


def validate_gold(gold: dict) -> None:
    from app.agent.intent import explicit_intent

    bad = []
    for c in gold["cases"]:
        direct = explicit_intent(c["text"])
        if direct.action != "chat":
            bad.append((c["id"], direct.action, c["text"][:50]))
    if bad:
        lines = ", ".join(f"{i}:{a}" for i, a, _ in bad)
        raise ValueError(f"Gold cases must use LLM path (explicit=chat). Bad: {lines}")


def make_examples(gold: dict) -> list[dict]:
    return [
        {
            "inputs": {
                "text": c["text"],
                "case_id": c["id"],
                "history": c.get("history") or [],
            },
            "reference_outputs": {
                "expect": c.get("expect") or {},
                "expect_any": c.get("expect_any") or {},
            },
            "metadata": {"case_id": c["id"]},
        }
        for c in gold["cases"]
    ]


def _normalize_outputs(outputs: dict | None) -> dict:
    """LangSmith sometimes stores failures as {'output': None} under concurrency."""
    if not isinstance(outputs, dict):
        return {}
    if outputs.get("action") is not None:
        return outputs
    inner = outputs.get("output")
    if isinstance(inner, dict):
        return inner
    return outputs


def _match_expect(outputs: dict, reference_outputs: dict) -> tuple[bool, str]:
    expect = reference_outputs.get("expect") or {}
    notes = []
    for key, want in expect.items():
        got = outputs.get(key)
        if got != want:
            notes.append(f"{key}: want {want!r}, got {got!r}")
    expect_any = reference_outputs.get("expect_any") or {}
    for key, needles in expect_any.items():
        blob = str(outputs.get(key) or "")
        if not any(n.casefold() in blob.casefold() for n in needles):
            notes.append(f"{key}: need one of {needles!r} in {blob!r}")
    return (not notes, "; ".join(notes))


def score_intent_match(outputs, reference_outputs):
    from app.agent.intent import explicit_intent

    outputs = _normalize_outputs(outputs)
    text = str(outputs.get("text") or "")
    if not text and outputs.get("action") is None:
        return {"key": "intent_match", "score": None, "comment": "missing outputs"}
    if text and explicit_intent(text).action != "chat":
        return {"key": "intent_match", "score": None, "comment": "explicit rule path (not LLM)"}
    ok, notes = _match_expect(outputs, reference_outputs)
    return {"key": "intent_match", "score": int(ok), "comment": notes or None}


def score_used_llm(outputs, _reference_outputs):
    from app.agent.intent import explicit_intent

    outputs = _normalize_outputs(outputs)
    text = str(outputs.get("text") or "")
    if not text:
        return {"key": "used_llm", "score": None}
    used = outputs.get("used_llm")
    if used is None:
        used = explicit_intent(text).action == "chat"
    return {"key": "used_llm", "score": int(bool(used))}


def make_judges(settings):
    from langchain_openai import ChatOpenAI
    import re

    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
        timeout=45,
        max_retries=1,
    )

    def ask(rule, **fields):
        data = "\n".join(f"{key}: {value}" for key, value in fields.items())
        response = model.invoke(
            "You are a strict intent-classification evaluator. "
            "Respond with exactly 1 (pass) or 0 (fail).\n" + rule + "\n" + data
        )
        match = re.fullmatch(r"\s*([01])\s*", str(response.content))
        if not match:
            raise ValueError(f"Invalid judge score: {response.content!r}")
        return int(match.group(1))

    def action_appropriate(outputs, reference_outputs):
        outputs = _normalize_outputs(outputs)
        if not outputs.get("action"):
            return {"key": "action_appropriate", "score": None, "comment": "missing model output"}
        expect = reference_outputs.get("expect") or {}
        return {
            "key": "action_appropriate",
            "score": ask(
                "Given the user message and the expected action label, "
                "does the model's action match the user's true intent?",
                message=outputs.get("text", ""),
                expected_action=expect.get("action", ""),
                model_action=outputs.get("action", ""),
                goal=outputs.get("goal", ""),
                topic=outputs.get("topic", ""),
            ),
        }

    return [action_appropriate]


_TARGET_LOCK = threading.Lock()
_EVAL_LOOP: asyncio.AbstractEventLoop | None = None


def _eval_loop() -> asyncio.AbstractEventLoop:
    global _EVAL_LOOP
    if _EVAL_LOOP is None or _EVAL_LOOP.is_closed():
        _EVAL_LOOP = asyncio.new_event_loop()
    return _EVAL_LOOP


def build_target(agent_factory):
    agent_holder: dict[str, object] = {"agent": None}

    def get_agent():
        if agent_holder["agent"] is None:
            agent_holder["agent"] = agent_factory()
        return agent_holder["agent"]

    async def _run(inputs: dict) -> dict:
        from app.agent.intent import explicit_intent

        text = inputs["text"]
        history = inputs.get("history") or []
        direct = explicit_intent(text)
        agent = get_agent()
        intent = await agent.detect_intent(text, history)
        used_llm = direct.action == "chat" and agent.mode == "langchain"
        data = intent.model_dump()
        data["text"] = text
        data["explicit_action"] = direct.action
        data["used_llm"] = used_llm
        return data

    def target(inputs: dict) -> dict:
        # Reuse one event loop — asyncio.run() per call closes the loop and breaks LangSmith workers.
        with _TARGET_LOCK:
            loop = _eval_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_run(inputs))

    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="LangSmith detect_intent (LLM) evaluation")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--dataset-prefix", default=DATASET_PREFIX)
    parser.add_argument("--judge", action="store_true", help="Add LLM judge on action appropriateness")
    args = parser.parse_args()

    if not os.getenv("LANGSMITH_API_KEY"):
        parser.error("Set LANGSMITH_API_KEY in your environment")

    root = EVAL_DIR.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.database import store
    from app.agent.service import StudyAgent
    from app.runtime_llm import active_settings

    settings = active_settings()
    if not (settings.llm_model and settings.llm_api_key):
        parser.error("Online LLM required (Settings or .env: model + API key).")

    raw = args.gold.read_bytes()
    gold = json.loads(raw)
    validate_gold(gold)
    dataset_hash = hashlib.sha256(raw).hexdigest()
    dataset_name = f"{args.dataset_prefix}-{dataset_hash[:12]}"

    os.environ["LANGSMITH_TRACING"] = "true"
    from langsmith import Client

    client = Client()
    if not client.has_dataset(dataset_name=dataset_name):
        client.create_dataset(
            dataset_name=dataset_name,
            description="LLM detect_intent gold; see docs/task-flow-evaluation.md",
        )
        client.create_examples(dataset_name=dataset_name, examples=make_examples(gold))

    def agent_factory():
        return StudyAgent(store.connect)

    evaluators = [score_used_llm, score_intent_match]
    if args.judge:
        evaluators.extend(make_judges(active_settings()))

    target = build_target(agent_factory)
    print(
        f"Dataset: {dataset_name} | cases: {len(gold['cases'])} | "
        f"model: {settings.llm_model} | judge: {args.judge}"
    )
    results = client.evaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=f"doudou-detect-intent{'-judge' if args.judge else ''}",
        metadata={"gold_sha256": dataset_hash, "model": settings.llm_model, "judge": args.judge},
        max_concurrency=1,
    )
    print(f"Experiment: {results.experiment_name}")
    print(
        "LangSmith → Datasets →", dataset_name,
        "→ Experiments →", results.experiment_name,
    )
    _write_summary(client, results.experiment_name)


def _write_summary(client, project_name: str) -> None:
    from collections import defaultdict

    out = EVAL_DIR / "out" / "detect-intent-langsmith-summary.json"
    agg: dict[str, dict] = defaultdict(lambda: {"sum": 0.0, "n": 0, "null": 0, "fails": []})
    cases: dict[str, dict] = {}
    runs = list(client.list_runs(project_name=project_name, is_root=True, limit=50))
    for run in runs:
        inner = (run.inputs or {}).get("inputs") or run.inputs or {}
        cid = inner.get("case_id", "?")
        outs = _normalize_outputs(run.outputs)
        cases[cid] = {"outputs": outs, "scores": {}}
        for fb in client.list_feedback(run_ids=[str(run.id)]):
            if fb.score is None:
                agg[fb.key]["null"] += 1
                continue
            agg[fb.key]["sum"] += float(fb.score)
            agg[fb.key]["n"] += 1
            cases[cid]["scores"][fb.key] = float(fb.score)
            if fb.score < 1:
                agg[fb.key]["fails"].append({"id": cid, "comment": fb.comment})
    missing = sum(1 for r in runs if not _normalize_outputs(r.outputs).get("action"))
    summary = {
        "experiment": project_name,
        "n_runs": len(runs),
        "runs_missing_action": missing,
        "metrics": {
            k: {
                "mean": v["sum"] / v["n"] if v["n"] else None,
                "n": v["n"],
                "null": v["null"],
                "fails": v["fails"],
            }
            for k, v in agg.items()
        },
        "cases": cases,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary: {out.resolve()}")
    if missing:
        print(f"WARNING: {missing} runs still missing action in outputs.", file=sys.stderr)


if __name__ == "__main__":
    main()