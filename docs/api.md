# API contract (v0.2)

Local backend: `http://127.0.0.1:8000`; OpenAPI at `/docs`. The renderer uses REST for tasks and preferences, WebSocket for chat and pet state. This is a single-user local prototype, not a remotely exposed service.

| Endpoint | Request | Response |
|---|---|---|
| `GET /health` | — | `{"status":"ok","agent_mode":"demo"}` or `langchain` |
| `GET /tasks` | — | Array of `{id,title,done}` |
| `POST /tasks` | `{"title":"复习索引"}` | Created task, HTTP 201 |
| `PATCH /tasks/{id}` | `{"done":true}` | `{id,done}`; 404 if absent |
| `GET /preferences/pet_name` | — | `{key,value}` |
| `PUT /preferences/pet_name` | `{"value":"小鲸"}` | `{key,value}` |
| `POST /plans/replan-drafts` | `{"days":2,"minutes_per_day":30}` | Draft with schedule and reason; HTTP 422 if unfinished tasks cannot fit |
| `POST /plans/replan-drafts/{id}/confirm` | — | Applies draft once; HTTP 409 if already applied or tasks changed |
| `POST /plans/drafts` | `{ "goal":"复习数据库", "days":3, "minutes_per_day":40 }` | New plan draft with daily steps; no tasks are written yet |
| `POST /plans/drafts/{id}/confirm` | — | Creates all draft tasks once; HTTP 409 on repeat |
| `PATCH /tasks/{id}` | `{ "title":"B+树", "estimated_minutes":20, "done":true }` | Updated task |
| `POST /focus` / `GET /focus` | `{ "minutes":25, "task_id":1 }` | Active timer and remaining seconds |
| `POST /focus/{id}/finish` | — | Ends active timer |
| `POST /reviews` | `{ "topic":"B+树" }` | One review question |
| `POST /reviews/{id}/answer` | `{ "answer":"叶子节点用链连接" }` | Feedback and result |

Replanning uses unfinished tasks only. A draft includes each task's previous and proposed day; creating it does not modify tasks. Confirmation updates the schedule transactionally. Current tasks default to 30 minutes, and the first version preserves existing task order. More nuanced priority, deadline and LLM intent extraction can be added behind the same confirmation contract.

`WS /ws/chat` accepts `{"type":"message","text":"帮我制定复习数据库的学习计划，3天每天30分钟"}` and routes clear planning commands into a `plan_draft` event. A replan command returns `kind: "replan"` and `draft.schedule`; new plans return `kind: "plan"` and `draft.steps`. A request missing its study topic receives a question and accepts the topic in the next message on the same socket. Without a model key only explicit command patterns route; with a key a structured model intent classifier handles other phrasing. Missing time constraints default to 3 days and 45 minutes per day. The explicit `plan_request` event is also supported. Drafts do not modify tasks until the corresponding REST `/confirm` call. Each event has `type`, `text`, `state`; `welcome` includes `mode`. Chat sends `thinking`, optional `tool`, then `plan_draft`, `reply` or `error`.

The demo agent is deterministic when `OPENAI_API_KEY` is absent. With a key, LangChain `create_agent` calls the configured OpenAI model. It discovers `list_study_tasks` and `get_focus_timer` through the in-process MCP adapter; local preview tools cover planning and replanning. RAG remains an interface.

The MCP server also registers creation, completion, and focus timer writes for external clients; those tools are intentionally excluded from the Agent tool list. The review skill currently has preset scoring points only for B+ trees and Hash indexes; other topics explicitly return `needs_review`. The intent classifier chooses a workflow; plan content is still created by the deterministic study_plan skill. Model selection accuracy remains unmeasured without real API credentials and a labeled evaluation set.
