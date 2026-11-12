# API contract v0.4 / conversation protocol 2

Single-user local prototype. API defaults to `http://127.0.0.1:8000`, WebSocket to `/ws/chat`. `GET /health` returns `status`, `agent_mode`, `version: "0.4.0"`, and `protocol_version: 2`. A configured model is not proof of a successful live API call.

## Conversation

```json
{
  "type": "message",
  "text": "B+树为什么适合范围查询？",
  "request_id": "unique-client-request-id",
  "session_id": null,
  "knowledge": true,
  "document_ids": ["document-id"]
}
```

- `session_id: null` creates a new conversation; a valid ID resumes saved history.
- Omit `document_ids` to inherit saved scope. `null` searches all usable documents, `[]` searches none, and a list restricts retrieval to those documents. Server validates ownership.
- `general: true` explicitly requests ordinary chat without document search. `knowledge: true` explicitly requests the knowledge workflow.
- A reply echoes `request_id` and contains `session_id`, `context: {document_ids, topic}`, `text`, `state`, `sources`, `answer_mode`, optional `warning`, `draft`, `kind`, `review`, `quiz`, and `next_step`.
- `mode` denotes application model configuration (`demo` / `langchain`); `answer_mode` denotes this answer's provenance.
- Long document workflows emit periodic status events; completed summary groups are cached. The client ignores replies from expired or superseded requests.
- Sources include `id`, `document_id`, `chunk_id`, `filename`, `page` (real PDF/slide page or null), `section`, `snippet`, and `score`. Retrieval scores are ranking signals, not answer probabilities.

Answer modes: `general`, `memory`, `extractive`, `llm`, `no_evidence`, `clarification`, `summary`, `extractive_overview`, `comparison`, `citation_fallback`, `model_error`, `review`, and `agent`.

`plan_request` remains supported with `payload: {goal, days, minutes_per_day}`, plus conversation/scope/request fields. It returns a `plan_draft`; tasks are saved only after confirmation.

The pet and main renderer share full message metadata, execution status, selected scope and pending-request state through `chatStore.ts`. Saved conversation scope/topic lives in SQLite. Renderer local storage is a convenience cache; durable history remains available through the history API.

## Knowledge and memory

| Method | Path | Behavior |
|---|---|---|
| GET | `/knowledge/health` | Configuration and supported-file status |
| GET / POST | `/knowledge/documents` | List / upload multipart field `file` |
| DELETE | `/knowledge/documents/{id}` | Remove original and index |
| POST | `/knowledge/documents/{id}/reindex` | Replace chunks atomically and invalidate summary cache |
| GET | `/knowledge/documents/{id}/chunks` | Parsed chunks with original locations |
| GET | `/knowledge/documents/{id}/overview` | Offline keywords and structural metadata |
| GET | `/knowledge/documents/{id}/source` | Download original file |
| POST | `/knowledge/search` | `{query, document_ids?, k?}`; returns `{sources}` |
| POST | `/knowledge/chat` | `{question, session_id?, document_ids?}`; saves answer and context |
| POST | `/knowledge/compare` | `{document_ids: [2–4 IDs], query?, session_id?}`; compares and saves scoped history |
| GET | `/knowledge/sessions` | List saved conversations |
| GET | `/knowledge/sessions/{id}/messages` | Full messages with metadata and original source snapshots |
| DELETE | `/knowledge/sessions/{id}` | Delete one conversation |
| GET / PUT | `/knowledge/sessions/{id}/context` | Read/update `{document_ids}` |
| GET / PUT | `/knowledge/preferences` | Read/update `{values: {key: value}}` |
| GET / POST | `/knowledge/memories` | Read/save explicit memories `{key, content, tags}` |
| DELETE | `/knowledge/memories/{id}` | Forget one memory |
| POST | `/knowledge/memories/search` | `{query, k?}` |
| GET / POST | `/knowledge/bookmarks` | List/save `{document_id, chunk_id?, note?}` |
| DELETE | `/knowledge/bookmarks/{id}` | Remove a bookmark |

Knowledge endpoints accept `X-User-Id` for local namespace isolation; WebSocket and study workflows currently use `local-user`. This is not an authentication scheme.

## Study workflows

Existing tasks, focus and plan routes remain available:

- `GET/POST /tasks`, `PATCH /tasks/{id}`.
- `POST /plans/drafts` accepts `{goal, days, minutes_per_day, document_ids?, session_id?}` and returns a draft with material source snapshots.
- `POST /plans/drafts/{id}/confirm` saves tasks once; repeated confirmation returns409.
- `POST /plans/replan-drafts` / `POST /plans/replan-drafts/{id}/confirm` propose/apply a time-budget-checked replan.
- `POST/GET /focus`, `POST /focus/{id}/finish`.
- `POST /reviews` accepts `{topic, document_ids?, session_id?}`.
- `POST /reviews/daily-quiz` and `/reviews/weak-point` optionally accept `{document_ids, session_id}`.
- `POST /reviews/{id}/answer` accepts `{answer}`. The question's stored snapshot supplies the rubric and evidence; the grader does not re-retrieve documents. Repeated answers return409.
- `GET /learning/next-step`, `GET /learning/streak`.

Review questions do not expose the reference answer or grading rubric before submission. Offline custom-material reviews retain answers for manual checking; built-in B+ tree / Hash exercises use labeled preset criteria. Model grading accepts paraphrases and checks contradictions. A waiting chat review is bound to its conversation; explicit document questions can interrupt it without being graded.

MCP tools expose document search, personal context and study operations. The agent cannot create/complete saved tasks directly; plan confirmation remains in the UI. Focus/review tools honor their explicit operation contracts.
