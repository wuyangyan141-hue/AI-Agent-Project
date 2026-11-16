"""Insert Demonstration and Discussion sections into Group9_Report.docx."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.shared import Inches

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"c:\Users\Keenrich4s\Downloads\Group9_Report.docx")
REPORT = SRC.with_name("Group9_Report_updated.docx")
BACKUP = SRC.with_name("Group9_Report_backup.docx")
FIG_DIR = ROOT / "docs" / "report-demo-ch2"

DEMO_BLOCKS: list[tuple[str, str, str | None]] = [
    (
        "4.1 Demo environment and material",
        (
            "We demonstrated DouDou on Windows 11 with Node.js 22 and the FastAPI backend at "
            "127.0.0.1:8000. The handout DSAI5205_Chapter2_2026.pdf (search techniques: BFS/DFS, "
            "heuristic search, genetic algorithms) was uploaded via the knowledge library. Online "
            "chat used qwen-plus (DashScope compatible API); retrieval used local BM25 unless a "
            "dedicated embedding model is configured. Reproducible API traces live in "
            "docs/report-demo-ch2/."
        ),
        None,
    ),
    (
        "4.2 Upload and indexing",
        (
            "The PDF was parsed into 66 chunks with slide/page metadata for citations. Overview "
            "keywords (Search, Goal, algorithm) confirmed successful ingest before Q&A."
        ),
        "fig01_upload_overview.png",
    ),
    (
        "4.3 Scoped Q&A with citations",
        (
            "Question: what is searching and what are goal/solution? Answer mode llm returned "
            "verbatim quotes from page 2 with [S1] markers. A BFS versus DFS question reused "
            "pages 20–21, including the S–B–G vs S–A–C–G route contrast."
        ),
        "fig02_qa_cited.png",
    ),
    (
        "4.4 Negative query",
        (
            "“What is the capital city on Mars?” under the same scope returned no_evidence, "
            "refusing to hallucinate and suggesting in-corpus topics only."
        ),
        "fig03_no_evidence.png",
    ),
    (
        "4.5 Full-chapter summary",
        (
            "Summary mode covered 66/66 chunks and synthesised blind search, informed search, "
            "gradient methods, and genetic algorithms with multi-slide citations."
        ),
        "fig04_summary.png",
    ),
    (
        "4.6 Plan draft and review",
        (
            "A two-day plan draft cited Chapter 2 pages (e.g., gradient search, BFS/DFS) but "
            "remained unconfirmed until the user accepts it. A short-answer review item was "
            "generated with frozen evidence snapshots."
        ),
        "fig05_plan_draft.png",
    ),
    (
        "4.7 BFS vs DFS comparison",
        (
            "Comparative answer highlighting memory demands of BFS and non-shortest-path behaviour "
            "of DFS, grounded in lecture slides."
        ),
        "fig07_bfs_dfs.png",
    ),
    (
        "4.8 Review item snapshot",
        (
            "Material-grounded review stem linked to uploaded PDF pages (API capture equivalent to "
            "the chat/review UI)."
        ),
        "fig06_review.png",
    ),
]

DISCUSSION_BLOCKS: list[tuple[str, str]] = [
    (
        "5.1 Design rationale",
        (
            "Learners need traceable answers and a single study loop, not disconnected chat and "
            "task tools. RAG externalises course PDFs; stateful routing separates commands, Q&A, "
            "plans, and review answers. Quote-level grounding mitigates citation hallucination [6]; "
            "draft-then-confirm planning matches real scheduling behaviour."
        ),
    ),
    (
        "5.2 Capabilities demonstrated on Chapter 2",
        (
            "The system ingested the PDF, answered in-scope questions with page-level citations, "
            "rejected an off-topic Mars question, summarised the full slide deck, produced an "
            "evidence-backed plan draft, and issued a review question. Online mode enabled structured "
            "LLM answers; offline retrieval still supported scoped search."
        ),
    ),
    (
        "5.3 Limitations",
        (
            "We did not measure learning outcomes. LLM answers can still misinterpret evidence even "
            "when quotes are valid. Without semantic embeddings, English questions that do not "
            "lexically overlap slides may return no_evidence (e.g., an irrelevant “supervised learning” "
            "prompt on a search chapter). Scanned PDFs, multi-user deployment, and guaranteed global "
            "summary fidelity on very long texts remain open."
        ),
    ),
    (
        "5.4 Future work",
        (
            "Embed UI controls for embedding models, add OCR, build a small DSAI5205 regression set, "
            "warn when user goals mismatch selected PDFs, and optionally attach a screen-recording "
            "walkthrough of the Electron pet window for presentation marking."
        ),
    ),
]


def normalise(text: str) -> str:
    return text.strip().lower().replace("presentation", "demonstration")


def find_para(doc: Document, *needles: str) -> int:
    wants = {n.lower() for n in needles}
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip().lower()
        if t in wants:
            return i
    return -1


def remove_range(doc: Document, start: int, end: int) -> None:
    for i in range(end - 1, start, -1):
        el = doc.paragraphs[i]._element
        el.getparent().remove(el)


def add_heading(doc: Document, index: int, text: str, *, level: int) -> None:
    p = doc.paragraphs[index].insert_paragraph_before(text)
    p.style = f"Heading {level}"


def add_body(doc: Document, index: int, text: str) -> None:
    doc.paragraphs[index].insert_paragraph_before(text)


def add_figure(doc: Document, index: int, caption: str, image_name: str) -> None:
    path = FIG_DIR / image_name
    if path.is_file():
        pic_p = doc.paragraphs[index].insert_paragraph_before("")
        pic_p.add_run().add_picture(str(path), width=Inches(6.2))
        cp = doc.paragraphs[index].insert_paragraph_before(caption)
        cp.style = "Caption"
    else:
        doc.paragraphs[index].insert_paragraph_before(
            f"[Screenshot pending: generate {image_name} via scripts/build_report_figures.py]"
        )


def insert_demo_content(doc: Document, anchor: int) -> None:
    pos = anchor + 1
    for heading, body, fig in DEMO_BLOCKS:
        add_heading(doc, pos, heading, level=2)
        pos += 1
        add_body(doc, pos, body)
        pos += 1
        if fig:
            add_figure(doc, pos, f"Figure — {heading}", fig)
            pos += 1


def insert_discussion_content(doc: Document, anchor: int) -> None:
    pos = anchor + 1
    for heading, body in DISCUSSION_BLOCKS:
        add_heading(doc, pos, heading, level=2)
        pos += 1
        add_body(doc, pos, body)
        pos += 1


def main() -> None:
    if not SRC.is_file():
        raise SystemExit("Group9_Report.docx not found in Downloads")
    if not BACKUP.is_file():
        shutil.copy2(SRC, BACKUP)

    py = ROOT / "services" / "api" / ".venv" / "Scripts" / "python.exe"
    subprocess.run([str(py), str(ROOT / "scripts" / "build_report_figures.py")], check=False)

    doc = Document(BACKUP)
    demo_i = find_para(doc, "presentation", "demonstration", "4 demonstration")
    disc_i = find_para(doc, "discussion", "5 discussion")
    ref_i = find_para(doc, "references")

    if demo_i < 0:
        demo_i = ref_i if ref_i >= 0 else len(doc.paragraphs) - 1
        doc.paragraphs[demo_i].insert_paragraph_before("4 Demonstration")
        demo_i = find_para(doc, "4 demonstration")

    doc.paragraphs[demo_i].text = "4 Demonstration"

    if disc_i < 0:
        stop = ref_i if ref_i >= 0 else len(doc.paragraphs)
        remove_range(doc, demo_i, stop)
        insert_demo_content(doc, demo_i)
        if ref_i >= 0:
            doc.paragraphs[ref_i].insert_paragraph_before("5 Discussion")
            disc_i = find_para(doc, "5 discussion")
        else:
            doc.add_paragraph("5 Discussion")
            disc_i = len(doc.paragraphs) - 1
    else:
        remove_range(doc, demo_i, disc_i)
        insert_demo_content(doc, demo_i)
        disc_i = find_para(doc, "discussion", "5 discussion")

    doc.paragraphs[disc_i].text = "5 Discussion"
    stop = ref_i if ref_i >= 0 else len(doc.paragraphs)
    if ref_i >= 0:
        disc_i = find_para(doc, "5 discussion")
        remove_range(doc, disc_i, ref_i)
    else:
        remove_range(doc, disc_i, len(doc.paragraphs))

    insert_discussion_content(doc, disc_i)
    doc.save(REPORT)


if __name__ == "__main__":
    main()