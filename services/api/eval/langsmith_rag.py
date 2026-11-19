"""LangSmith evaluation of the real KnowledgeService search + answer path.

Run from services/api: python -m eval.langsmith_rag
Install optional dependency first: pip install "langsmith>=0.3,<1"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from .rag_benchmark import DEFAULT_GOLD, EVAL_DIR

USER = "langsmith-eval"


def make_examples(gold):
    """Reuse the existing fixture, keeping retrieval and answer cues separate."""
    return [
        {
            "inputs": {"question": c["question"], "case_id": c["id"]},
            "reference_outputs": {
                "kind": c["kind"],
                "retrieval_cues": c.get("must_retrieve_any", []),
                "answer_cues": c.get("must_answer_any", []),
            },
            "metadata": {"kind": c["kind"]},
        }
        for c in gold["cases"]
    ]


def cue_match(text, cues):
    return any(cue.casefold() in text.casefold() for cue in cues if cue)


def score_retrieval(outputs, reference_outputs):
    kind = reference_outputs["kind"]
    hits = outputs["retrieved"]
    if kind == "off_topic":
        return {"key": "retrieval_rejection", "score": int(not hits)}
    cues = reference_outputs["retrieval_cues"]
    return {"key": "retrieval_cue_at_k", "score": int(cue_match("\n".join(hits), cues))}


def score_answer(outputs, reference_outputs):
    kind = reference_outputs["kind"]
    if kind == "off_topic":
        return {"key": "refusal_accuracy", "score": int(outputs["mode"] == "no_evidence")}
    cues = reference_outputs["answer_cues"]
    return {"key": "answer_cue", "score": int(
        outputs["mode"] not in {"no_evidence", "model_error"}
        and cue_match(outputs["answer"], cues)
    )}


def score_citation(outputs, reference_outputs):
    if reference_outputs["kind"] == "off_topic":
        return {"key": "citation_presence", "score": None}
    if outputs["mode"] != "llm":
        return {"key": "citation_presence", "score": None}
    source_ids = {s["id"] for s in outputs["sources"]}
    import re
    cited = set(re.findall(r"\[(S\d+)\]", outputs["answer"]))
    return {"key": "citation_presence", "score": int(bool(cited) and cited <= source_ids)}


def build_target(gold, settings):
    from app.knowledge.service import KnowledgeService
    from langsmith import traceable

    kb = KnowledgeService(settings)
    corpus = EVAL_DIR / gold.get("corpus_file", "corpus/search_basics.txt")
    document = kb.upload(USER, corpus.name, corpus.read_bytes())
    if document["status"] != "ready":
        raise RuntimeError("Corpus indexing failed")
    doc_id = document["id"]

    @traceable(name="knowledge_search", run_type="retriever")
    def retrieve(question):
        return kb.search(USER, question, [doc_id])

    @traceable(name="rag_search_and_answer")
    def target(inputs):
        question = inputs["question"]
        start = time.perf_counter()
        retrieved = retrieve(question)
        # Every example gets a fresh session, so history cannot leak between cases.
        result = kb.answer(USER, question, document_ids=[doc_id], operation="qa")
        return {
            "answer": result["answer"],
            "mode": result["mode"],
            "sources": result.get("sources", []),
            "retrieved": [hit["snippet"] for hit in retrieved],
            "latency_ms": round((time.perf_counter() - start) * 1000),
        }

    return target, kb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--mode", choices=["offline", "configured"], default="offline")
    parser.add_argument("--dataset-prefix", default="doudou-rag")
    args = parser.parse_args()

    if not os.getenv("LANGSMITH_API_KEY"):
        parser.error("Set LANGSMITH_API_KEY in your environment")
    os.environ["LANGSMITH_TRACING"] = "true"
    from langsmith import Client
    from app.knowledge.config import Settings

    raw = args.gold.read_bytes()
    gold = json.loads(raw)
    dataset_name = f"{args.dataset_prefix}-{hashlib.sha256(raw).hexdigest()[:12]}"
    client = Client()
    if not client.has_dataset(dataset_name=dataset_name):
        client.create_dataset(dataset_name=dataset_name, description="Fixed DouDou RAG fixture; see docs/langsmith-rag-evaluation.md")
        client.create_examples(dataset_name=dataset_name, examples=make_examples(gold))

    root = Path(tempfile.mkdtemp(prefix="doudou-langsmith-"))
    configured = Settings.from_env()
    from dataclasses import replace
    settings = replace(
        configured,
        data_dir=root / "knowledge",
        database_path=root / "bench.db",
        **({"embedding_provider": "local", "llm_model": "", "llm_api_key": ""}
           if args.mode == "offline" else {}),
    )
    if args.mode == "configured" and not settings.llm_model:
        parser.error("Configured mode needs LLM_MODEL and a working model API key")
    target, kb = build_target(gold, settings)
    status = kb.status()
    print(f"Dataset: {dataset_name} | mode: {args.mode} | retrieval: {status['retrieval_mode']} | answer: {status['answer_mode']}")
    results = client.evaluate(
        target,
        data=dataset_name,
        evaluators=[score_retrieval, score_answer, score_citation],
        experiment_prefix=f"doudou-{args.mode}",
        metadata={"mode": args.mode, "embedding_id": kb.embedding_id, "gold_sha256": hashlib.sha256(raw).hexdigest()},
        max_concurrency=1,
    )
    print(f"Experiment: {results.experiment_name}")
    print("Inspect per-example scores and failures in LangSmith Datasets > Experiments.")


if __name__ == "__main__":
    main()
