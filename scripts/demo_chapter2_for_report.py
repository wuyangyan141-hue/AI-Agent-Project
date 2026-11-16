"""Upload DSAI5205 Ch2 PDF, run demo API calls, save evidence for report."""
from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"
PDF = Path(r"c:\Users\Keenrich4s\Downloads\5205\DSAI5205_Chapter2_2026.pdf")
OUT = Path(__file__).resolve().parents[1] / "docs" / "report-demo-ch2"
USER = "local-user"
HEADERS = {"X-User-Id": USER}


def save_json(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_panel(name: str, title: str, body: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        (OUT / f"{name}.txt").write_text(f"{title}\n\n{body}", encoding="utf-8")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
    ax.axis("off")
    wrapped = "\n".join(textwrap.wrap(body, width=92))
    ax.text(
        0.02,
        0.98,
        f"{title}\n\n{wrapped}",
        va="top",
        ha="left",
        fontsize=9,
        family="sans-serif",
        transform=ax.transAxes,
    )
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", facecolor="#f8f9fb")
    plt.close(fig)


def upload_pdf(client: httpx.Client) -> dict:
    with PDF.open("rb") as f:
        r = client.post(
            f"{API}/knowledge/documents",
            headers=HEADERS,
            files={"file": (PDF.name, f, "application/pdf")},
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


def wait_ready(client: httpx.Client, doc_id: str, timeout_s: float = 180) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        docs = client.get(f"{API}/knowledge/documents", headers=HEADERS, timeout=30).json()
        row = next((d for d in docs if d["id"] == doc_id), None)
        if not row:
            raise RuntimeError("document missing after upload")
        if row.get("status") == "ready":
            return row
        if row.get("status") == "error":
            raise RuntimeError(row.get("error") or "indexing failed")
        time.sleep(0.5)
    raise TimeoutError("indexing timeout")


def chat(client: httpx.Client, question: str, document_ids: list[str] | None) -> dict:
    body: dict = {"question": question}
    if document_ids is not None:
        body["document_ids"] = document_ids
    r = client.post(f"{API}/knowledge/chat", headers=HEADERS, json=body, timeout=120)
    r.raise_for_status()
    return r.json()


def overview(client: httpx.Client, doc_id: str) -> dict:
    r = client.get(f"{API}/knowledge/documents/{doc_id}/overview", headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def plan_draft(client: httpx.Client, doc_id: str) -> dict:
    r = client.post(
        f"{API}/plans/drafts",
        headers=HEADERS,
        json={
            "goal": "Review DSAI5205 Chapter 2 supervised learning",
            "days": 2,
            "minutes_per_day": 45,
            "document_ids": [doc_id],
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def review(client: httpx.Client, doc_id: str) -> dict:
    r = client.post(
        f"{API}/reviews",
        headers=HEADERS,
        json={"topic": "supervised learning from lecture notes", "document_ids": [doc_id]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def fmt_answer(payload: dict) -> str:
    mode = payload.get("mode") or payload.get("answer_mode") or "?"
    warning = payload.get("warning") or ""
    text = (payload.get("answer") or payload.get("text") or "")[:1200]
    sources = payload.get("sources") or []
    src_lines = []
    for s in sources[:4]:
        page = s.get("page")
        src_lines.append(
            f"- {s.get('id', '?')} {s.get('filename', '')} p.{page} score={s.get('score')}"
        )
    block = f"mode: {mode}\n"
    if warning:
        block += f"warning: {warning}\n"
    block += f"\n{text}\n"
    if src_lines:
        block += "\nSources:\n" + "\n".join(src_lines)
    return block


def main() -> None:
    if not PDF.is_file():
        raise SystemExit(f"PDF not found: {PDF}")
    with httpx.Client() as client:
        health = client.get(f"{API}/health", timeout=10).json()
        khealth = client.get(f"{API}/knowledge/health", timeout=10).json()
        save_json("00_health.json", {"health": health, "knowledge_health": khealth})

        docs = client.get(f"{API}/knowledge/documents", headers=HEADERS).json()
        existing = next((d for d in docs if d.get("filename") == PDF.name), None)
        if existing and existing.get("status") == "ready":
            doc = existing
            save_json("01_upload_skipped.json", doc)
        else:
            doc = upload_pdf(client)
            save_json("01_upload.json", doc)
            doc = wait_ready(client, doc["id"])

        doc_id = doc["id"]
        ov = overview(client, doc_id)
        save_json("02_overview.json", ov)
        save_panel(
            "fig01_upload_overview",
            "Figure 1 · Document ingest (DSAI5205 Chapter 2)",
            f"File: {PDF.name}\nStatus: {doc.get('status')} · chunks: {doc.get('chunk_count')}\n"
            f"Keywords: {', '.join((ov.get('keywords') or [])[:12])}\n"
            f"Backend: agent_mode={health.get('agent_mode')}, embedding={khealth.get('embedding_mode')}",
        )

        q1 = (
            "According to this chapter, what is supervised learning and how does it "
            "differ from unsupervised learning?"
        )
        r1 = chat(client, q1, [doc_id])
        save_json("03_qa_supervised.json", r1)
        save_panel("fig02_qa_cited", "Figure 2 · Scoped Q&A with citations", fmt_answer(r1))

        q2 = "What is the capital city on Mars?"
        r2 = chat(client, q2, [doc_id])
        save_json("04_qa_irrelevant.json", r2)
        save_panel("fig03_no_evidence", "Figure 3 · Out-of-scope query (negative case)", fmt_answer(r2))

        q3 = "Summarise the main topics in this chapter."
        r3 = chat(client, q3, [doc_id])
        save_json("05_summary.json", r3)
        save_panel("fig04_summary", "Figure 4 · Chapter overview request", fmt_answer(r3))

        draft = plan_draft(client, doc_id)
        save_json("06_plan_draft.json", draft)
        steps = draft.get("steps") or draft.get("schedule") or []
        plan_text = "\n".join(
            f"Day {s.get('day')}: {s.get('title')} ({s.get('minutes')} min)" for s in steps[:6]
        )
        save_panel(
            "fig05_plan_draft",
            "Figure 5 · Study plan draft (unconfirmed)",
            f"Goal: Review DSAI5205 Chapter 2\n{plan_text or str(draft)[:800]}",
        )

        rev = review(client, doc_id)
        save_json("07_review_question.json", rev)
        stem = rev.get("stem") or rev.get("question") or ""
        save_panel(
            "fig06_review",
            "Figure 6 · Material-grounded review item",
            f"Question type: {rev.get('question_type')}\n\n{stem[:900]}",
        )

        save_json(
            "summary_for_report.json",
            {
                "document_id": doc_id,
                "filename": PDF.name,
                "demos": [
                    "upload_and_overview",
                    "scoped_qa_supervised_vs_unsupervised",
                    "negative_mars_question",
                    "chapter_summary",
                    "plan_draft",
                    "review_question",
                ],
            },
        )
    print("Done. Evidence in", OUT)


if __name__ == "__main__":
    main()