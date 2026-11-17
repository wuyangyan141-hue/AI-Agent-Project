# 4 Demonstration / 5 Discussion (draft for Group 9 report)

Paste into the course report. Replace `[Figure N]` with your screenshots, or keep the existing panels under `docs/report-demo-ch2/`. If you submit a screen recording, insert one sentence under §4.1 pointing to the video filename/URL.

---

## 4 Demonstration

### 4.1 Demo environment and material

We demonstrated **DouDou** (豆豆), a local learning companion, on Windows 11 with Node.js 22 and a FastAPI backend at `127.0.0.1:8000`. The Electron desktop app hosts a floating pet window and a full chat/workspace window that share the same conversation state. Course material for the demo was the lecture PDF **DSAI5205_Chapter2_2026.pdf** (search techniques: definitions of searching, BFS/DFS, heuristic/gradient methods, genetic algorithms). Online answering used a compatible chat model (`qwen-plus` via DashScope-compatible API); retrieval used local BM25 unless a dedicated embedding model is configured. Reproducible API traces for this chapter are stored in `docs/report-demo-ch2/`.

*[Optional video: A short screen recording of the walkthrough below is submitted as `<filename>`; timestamps correspond to subsections 4.2–4.8.]*

### 4.2 Upload and indexing

The PDF was uploaded through the knowledge library / learning-folder sidebar. The backend parsed the file into indexed chunks with real page (or slide) metadata. An overview confirmed readiness (status `ready`, chunk count, keywords such as Search / Goal / algorithm) before any Q&A. This step shows that the system treats course PDFs as a first-class knowledge base rather than ephemeral chat attachments.

**[Figure 1 — Upload & index overview]**  
*(e.g. `fig01_upload_overview.png` or a desktop screenshot of the document card.)*

### 4.3 Scoped Q&A with citations

With the Chapter 2 document in scope, we asked: *What is searching, and what are the goal and solution in this chapter?* The answer mode was `llm` (when a model key is configured): the reply included verbatim quotes tied to **page 2** and clickable `[S#]` citation markers. Opening a citation shows the supporting snippet. A second in-scope question compared **BFS vs DFS**, grounding the answer in later slides (e.g. pages 20–21) and the route contrast S–B–G vs S–A–C–G.

**[Figure 2 — Scoped Q&A with citations]**  
**[Figure 7 — BFS vs DFS comparison]** *(if shown separately)*

### 4.4 Negative query (no hallucination)

Under the same document scope we asked an out-of-corpus question: *What is the capital city on Mars?* The system returned `no_evidence` (or equivalent “资料不足” UX): it refused to invent an answer and only pointed toward topics present in the uploaded material. This demonstrates honesty constraints in the RAG pipeline.

**[Figure 3 — Negative / no-evidence reply]**

### 4.5 Full-chapter summary

We requested a chapter-level overview. Summary coverage used all indexed chunks of the PDF (66/66 in our captured run) and synthesised themes across blind search, informed/heuristic search, gradient-style methods, and genetic algorithms, with multi-page citations where applicable.

**[Figure 4 — Full-chapter summary]**

### 4.6 Study plan draft (human-in-the-loop)

We asked the companion to draft a short study plan (e.g. *2 days, 45 minutes per day*, goal tied to Chapter 2). Intent routing treated this as a **plan** command rather than document Q&A. The UI showed a **draft** with day-by-day steps grounded in lecture topics (e.g. gradient search, BFS/DFS). Tasks are **not** written until the user confirms (“就用这版” / confirm); the panel can be cancelled or closed so the draft does not block the chat. This matches a draft-then-confirm workflow for scheduling.

**[Figure 5 — Plan draft HITL / confirm UI]**

### 4.7 Daily quiz (multiple choice, sequential)

We triggered **今日小测** (daily quiz). The system summarised relevant knowledge points, then issued **multiple-choice** items grounded in the uploaded PDF. Only the current question is waiting for an answer; remaining items stay queued so ordinary chat is not graded as an answer. After each submission (or “下一题”), the next item appears with progress (e.g. 第 2/3 题); finishing the set reports a short score summary. Grading uses a frozen snapshot of the question, options, and evidence rather than re-retrieving at mark time.

**[Figure 6 — Quiz question with options / progress]**

### 4.8 Desktop pet and study loop (optional on slides)

The floating pet mirrors chat turns and quick actions (today’s plan, quiz, review, focus check-in). Completing a timed focus session linked to a task can offer a short follow-up question about that task when the materials support it. Together with the sidebar learning folders and the bottom “学习路线” care rail, this shows the intended loop: **upload → ask → plan → focus → quiz/review**.

**[Figure 8 — Pet bubble + main window sync]** *(one screenshot is enough)*

---

## 5 Discussion

### 5.1 Why this design is appropriate

Course study is not only “chat with a PDF.” Learners need (1) **traceable** answers they can check against slides, (2) a **single loop** from materials to practice, and (3) **safe refusals** when the corpus cannot support an answer. DouDou’s architecture separates concerns with intent-first routing: plan / focus / quiz / review commands do not force RAG on every utterance, while explicit knowledge questions use retrieval with quote checks. Draft-then-confirm planning avoids silently rewriting the user’s task list. Freezing quiz evidence at generation time makes grading stable and auditable. The desktop pet is a lightweight presence layer on the same protocol, not a second disconnected product.

### 5.2 What the system can do

On DSAI5205 Chapter 2 we showed that DouDou can:

- ingest a lecture PDF into page-aware chunks and expose them in a learning folder;
- answer in-scope questions with page-level citations (and compare BFS/DFS from the same deck);
- refuse off-topic questions without fabricating facts;
- summarise the full indexed chapter when requested;
- draft a material-grounded study plan that requires human confirmation;
- run a short multiple-choice quiz on document knowledge points, one question at a time, with scored feedback;
- keep pet UI and main window aligned on the same conversation and HITL flows.

Offline (no API key), lexical retrieval and extractive overviews still work; online mode adds structured LLM answers, summary synthesis, and stronger quiz generation.

### 5.3 What the system cannot do (limitations)

- We did **not** measure learning outcomes (retention, exam scores, or time-on-task studies).
- Even with valid quotes, the LLM may **misinterpret** evidence; grounding reduces citation hallucination but does not guarantee perfect pedagogy.
- Without semantic embeddings, English prompts that do not **lexically overlap** the slides may yield `no_evidence` (e.g. asking “supervised learning” on a search chapter).
- Scanned PDFs without OCR, very long documents under tight context budgets, and **multi-user / cloud** deployment are out of scope for this single-user local prototype.
- Quiz quality still depends on keyword/topic extraction quality; thin or poorly structured PDFs produce weaker items.

### 5.4 What we would improve

1. **Stronger retrieval for course English** — default hybrid BM25 + embeddings with a small DSAI5205 regression set of gold Q&A.
2. **Richer quiz authoring** — paraphrased correct options (not only cloze/copy), distractors from nearby misconceptions, and jump-to-page from each option.
3. **OCR and format coverage** — scanned slides and legacy Office files without manual conversion.
4. **Mismatch warnings** — if the user’s plan goal contradicts the selected PDF topics, surface an explicit warning.
5. **Evaluation harness** — automated checks for citation support rate, plan confirm UX, and quiz queue behaviour, plus an optional submitted video walkthrough for presentation marking.

---

## Screenshot checklist (for slides / Word)

| ID | Content to capture |
|----|--------------------|
| Fig.1 | Document ready: filename, chunks, keywords |
| Fig.2 | In-scope Q&A with `[S#]` / source pills (page 2) |
| Fig.3 | Mars / off-topic → no evidence |
| Fig.4 | Chapter summary reply |
| Fig.5 | Plan draft panel (preview + confirm/cancel) |
| Fig.6 | Daily quiz MC item (options + “第 n/N 题”) |
| Fig.7 | BFS vs DFS cited answer *(optional if Fig.2 already shows citations)* |
| Fig.8 | Pet window + same turn *(optional)* |

API-rendered backups: `docs/report-demo-ch2/fig01_*.png` … `fig07_*.png`. Prefer live desktop screenshots for the oral presentation.
