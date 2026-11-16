"""Render demo evidence panels as PNG for the report."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "docs" / "report-demo-ch2"


def load(name: str) -> dict:
    return json.loads((EVID / name).read_text(encoding="utf-8"))


def panel(path: Path, title: str, body: str, *, width: int = 1100, height: int = 720) -> None:
    img = Image.new("RGB", (width, height), "#f5f7fb")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arial.ttf", 22)
        font_body = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
    draw.rectangle((0, 0, width, 56), fill="#2c3e50")
    draw.text((20, 16), title, fill="white", font=font_title)
    y = 72
    for line in textwrap.wrap(body, width=110):
        draw.text((24, y), line, fill="#1a1a1a", font=font_body)
        y += 22
        if y > height - 24:
            draw.text((24, y), "…", fill="#666", font=font_body)
            break
    img.save(path)


def main() -> None:
    EVID.mkdir(parents=True, exist_ok=True)
    health = load("00_health.json")
    ov = load("02_overview.json")
    q_search = load("08_qa.json")
    q_bfs = load("09_qa.json")
    q_mars = load("04_qa_irrelevant.json")
    summary = load("05_summary.json")
    plan = load("06_plan_draft.json")
    review = load("07_review_question.json")

    panel(
        EVID / "fig01_upload_overview.png",
        "Figure 1 · Upload & index (DSAI5205 Chapter 2)",
        f"File: DSAI5205_Chapter2_2026.pdf\n"
        f"Chunks indexed: {summary['coverage']['total_chunks']}\n"
        f"Keywords: {', '.join(ov['keywords'][:10])}\n"
        f"Runtime: qwen-plus online; retrieval={health['knowledge_health']['retrieval_mode']}",
    )
    s1 = q_search["sources"][0]
    panel(
        EVID / "fig02_qa_cited.png",
        "Figure 2 · Scoped Q&A with citations (page 2)",
        f"Q: What is searching and what are goal/solution?\n"
        f"Mode: {q_search['mode']}\n\n"
        f"A: {q_search['answer']}\n\n"
        f"Source {s1['id']}: {s1['filename']} p.{s1['page']}\n"
        f"Excerpt: {s1['snippet'][:280]}…",
    )
    panel(
        EVID / "fig03_no_evidence.png",
        "Figure 3 · Negative query (no hallucination)",
        f"Q: What is the capital city on Mars?\n"
        f"Mode: {q_mars['mode']}\n\n"
        f"A: {q_mars['answer']}",
    )
    panel(
        EVID / "fig04_summary.png",
        "Figure 4 · Full-chapter summary (66/66 chunks)",
        f"Mode: {summary['mode']}\n"
        f"Coverage: {summary['coverage']['processed_chunks']}/{summary['coverage']['total_chunks']} chunks\n\n"
        f"{(summary.get('answer') or '')[:650]}…",
    )
    steps = plan.get("steps") or []
    plan_lines = "\n".join(f"Day {s['day']}: {s['title'][:70]}… ({s['minutes']} min)" for s in steps)
    panel(
        EVID / "fig05_plan_draft.png",
        "Figure 5 · Plan draft tied to Chapter 2 (not saved yet)",
        f"Goal: {plan.get('goal')}\n{plan_lines}\n\n"
        f"Evidence snapshot pages: {', '.join(str(s.get('page')) for s in (plan.get('sources') or [])[:3])}",
    )
    panel(
        EVID / "fig06_review.png",
        "Figure 6 · Review question grounded in uploaded PDF",
        f"Topic: {review.get('topic')}\n"
        f"Type: {review.get('question_type')}\n\n"
        f"{(review.get('stem') or review.get('question') or '')[:520]}…",
    )
    bfs = q_bfs["sources"][0]
    panel(
        EVID / "fig07_bfs_dfs.png",
        "Figure 7 · BFS vs DFS comparison (pages 20–21)",
        f"Mode: {q_bfs['mode']}\n\n"
        f"{q_bfs['answer']}\n\n"
        f"Primary source p.{bfs['page']}: {bfs['snippet'][:220]}…",
    )


if __name__ == "__main__":
    main()