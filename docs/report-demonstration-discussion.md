# 4 Demonstration / 5 Discussion (draft for Group 9 report)

Paste into the course report. Replace `[Figure N]` with your screenshots, or keep the existing panels under `docs/report-demo-ch2/`. If you submit a screen recording, insert one sentence under §4.1 pointing to the video filename/URL.

---

## 4 Demonstration

### 4.1 Demo environment and material

We demonstrated **doudou** (豆豆), a local learning companion, on Windows 11 with Node.js 22 and a FastAPI backend at `127.0.0.1:8000`. The Electron desktop app hosts a floating pet window and a full chat/workspace window that share the same conversation state. Course material for the demo was the lecture PDF **DSAI5205_Chapter2_2026.pdf** (search techniques: definitions of searching, BFS/DFS, heuristic/gradient methods, genetic algorithms). Online answering used a compatible chat model (`qwen-plus` via DashScope-compatible API); retrieval used local BM25 unless a dedicated embedding model is configured. Reproducible API traces for this chapter are stored in `docs/report-demo-ch2/`.

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

### 5.1 Positioning: a study loop, not a chat toy

The design question for doudou was whether a desktop companion should behave like a general chatbot with documents attached, or like a local study loop that keeps materials, scheduling, practice, and presence in one place. We chose the latter. Self-directed study often fails when answers cannot be checked against source pages, when plans rewrite a learner’s schedule without consent, and when quizzes collide with ordinary chat because assessment state is not isolated. The companion is therefore organised as a continuous workflow in which learners upload materials, ask with citations, receive a clear refusal when the corpus cannot support an answer, confirm plans before tasks are written, and then move into focus, quiz, or review, rather than as a set of disconnected features.

Intent-first routing is what makes that workflow workable. Plan, focus, quiz, and review are handled as dedicated flows, while only explicit knowledge questions enter the retrieval path with quote checks. Asking for a multi-day plan must not be answered as if it were a definition question about the document, and advancing a quiz must not be graded as an option letter. The floating pet shares the same conversation and human-in-the-loop protocol as the main window, so presence remains a thin client of one system rather than a second product.

### 5.2 What the system demonstrates in practice

Without tying the argument to any single lecture file, the prototype shows several behaviours that matter for a study companion. In-scope questions return answers with page- or snippet-linked citations, and opening a citation reveals the supporting passage, so the learner can verify the model against the material instead of trusting fluent prose alone. When the indexed corpus cannot support a question, the system returns a no-evidence response rather than inventing facts; for study tools, a clear refusal is preferable to a confident hallucination. Study plans are drafted from goals and available materials, but tasks are written only after the user confirms, and cancelling or closing the draft leaves the task list unchanged, which matches how learners negotiate workload in practice. Daily quizzes and reviews prefer objective items, show one waiting question at a time, and keep remaining items queued so normal chat is not mis-scored; each item freezes its stem, options, and evidence at generation time, which keeps grading auditable even if later retrieval would return different chunks.

Offline mode still supports lexical retrieval and extractive overviews, while online mode adds structured synthesis and stronger free-form generation when an API is configured. The same local stack therefore remains usable with or without a cloud model.

### 5.3 Limitations

The scope of this work should be read carefully. We evaluated system behaviour and interaction design through demonstration and a small offline RAG sample; we did not run a controlled study of learning outcomes such as retention or exam performance. Answer quality still depends on the configured model and on how clearly the uploaded material states a point, even when citations are present. The default local setup favours lexical retrieval and optional embeddings, which is enough for the prototype but leaves room for stronger semantic matching in later releases. The current build targets a single-user desktop companion: very large libraries, multi-user sync, and cloud tenancy were not design goals for this version.

### 5.4 Design trade-offs

Several trade-offs shaped the shipped behaviour. Keeping the companion and knowledge base on-device preserves privacy and offline study, at the cost of weaker default semantics without embeddings or an API key. Requiring plan confirmation slows one-click scheduling, but avoids rewriting a learner’s week without consent. Queuing quiz items and freezing evidence add interface state, yet they prevent chat turns from being graded as answers—a failure mode that is easy to ignore in chatbot demos and costly in real use. In each case we favoured inspectability and consent over maximum automation.

### 5.5 Future work

Looking ahead, we would extend the same study loop rather than redesign it. Hybrid retrieval with stronger embeddings can deepen cross-language and paraphrase understanding while keeping page-linked citations. The small-sample RAG suite in `docs/rag-benchmark-results.md` can grow into a regular regression check as more course packs are added. Quiz generation can become richer—more varied stems, clearer knowledge-point options, and one-click jumps from an answer back to the source page. Broader document intake (including OCR and additional office formats) would let learners keep more of their materials inside one companion. On the product side, clearer goal–material coaching before plan confirm, and lightweight automated checks for citation support and HITL flows, would help each release stay aligned with the behaviours shown in the demonstration.

Taken together, the work suggests that a local companion can make study materials checkable, schedulable with consent, and practisable without breaking chat, when routing, grounding, and assessment state are treated as first-class parts of the design.

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
