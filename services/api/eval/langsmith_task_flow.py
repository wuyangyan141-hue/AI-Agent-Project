"""LangSmith evaluation for deterministic task-flow routing (intent / route / turn).

No LLM calls — tracks regressions in LangSmith Datasets & Experiments.

Run from services/api:
  python -m eval.langsmith_task_flow
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from .corpus_loader import EVAL_DIR
from .task_flow_benchmark import DEFAULT_GOLD, _load_gold, _match, evaluate_case

DATASET_PREFIX = "doudou-taskflow"


def make_examples(gold: dict) -> list[dict]:
    return [
        {
            "inputs": {"text": c["text"], "case_id": c["id"], "layer": c["layer"]},
            "reference_outputs": {
                "expect": c.get("expect") or {},
                "layer": c["layer"],
            },
            "metadata": {"layer": c["layer"], "notes": c.get("notes") or ""},
        }
        for c in gold["cases"]
    ]


def score_routing_match(outputs, reference_outputs):
    expect = reference_outputs.get("expect") or {}
    actual = outputs.get("actual") or {}
    ok, notes = _match(expect, actual)
    return {"key": "routing_match", "score": int(ok), "comment": notes or None}


def score_layer(outputs, reference_outputs):
    layer = reference_outputs.get("layer", "")
    if outputs.get("layer") != layer:
        return {"key": "layer_ok", "score": 0}
    return {"key": "layer_ok", "score": 1}


def build_target(cases_by_id: dict[str, dict]):
    from langsmith import traceable

    @traceable(name="task_flow_dispatch")
    def target(inputs: dict):
        case_id = inputs["case_id"]
        case = cases_by_id[case_id]
        result = evaluate_case(case)
        return {
            "layer": result.layer,
            "actual": result.actual,
            "passed": result.passed,
            "notes": result.notes,
        }

    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload task-flow gold set to LangSmith and evaluate")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--dataset-prefix", default=DATASET_PREFIX)
    args = parser.parse_args()

    if not os.getenv("LANGSMITH_API_KEY"):
        parser.error("Set LANGSMITH_API_KEY in your environment")

    root = EVAL_DIR.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    os.environ["LANGSMITH_TRACING"] = "true"
    from langsmith import Client

    raw = args.gold.read_bytes()
    gold = json.loads(raw)
    dataset_hash = hashlib.sha256(raw).hexdigest()
    dataset_name = f"{args.dataset_prefix}-{dataset_hash[:12]}"

    client = Client()
    if not client.has_dataset(dataset_name=dataset_name):
        client.create_dataset(
            dataset_name=dataset_name,
            description="Task-flow routing fixture; see docs/task-flow-evaluation.md",
        )
        client.create_examples(dataset_name=dataset_name, examples=make_examples(gold))

    cases_by_id = {c["id"]: c for c in gold["cases"]}
    target = build_target(cases_by_id)
    print(f"Dataset: {dataset_name} | cases: {len(cases_by_id)} | mode: deterministic (no LLM)")
    results = client.evaluate(
        target,
        data=dataset_name,
        evaluators=[score_routing_match, score_layer],
        experiment_prefix="doudou-taskflow",
        metadata={"gold_sha256": dataset_hash, "suite": gold.get("name")},
        max_concurrency=4,
    )
    print(f"Experiment: {results.experiment_name}")
    print(
        "Open LangSmith → Datasets →", dataset_name,
        "→ Experiments →", results.experiment_name,
        "(Tracing project name usually matches the experiment name.)",
    )


if __name__ == "__main__":
    main()