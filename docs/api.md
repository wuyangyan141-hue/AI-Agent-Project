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

Replanning uses unfinished tasks only. A draft includes each task's previous and proposed day; creating it does not modify tasks. Confirmation updates the schedule transactionally. Current tasks default to 30 minutes, and the first version preserves existing task order. More nuanced priority, deadline and LLM intent extraction can be added behind the same confirmation contract.

`WS /ws/chat` accepts `{"type":"message","text":"复习数据库"}`. The server sends `welcome` (`state: idle`), then `status` (`state: thinking`), then `reply` (`state: success`) or `error` (`state: error`). Each event has `type`, `text`, `state`; `welcome` also includes `mode`. Future states `searching` and `tool` are reserved in the renderer for later retrieval/tool events; this scaffold does not emit them yet.

The demo agent is deterministic when `OPENAI_API_KEY` is absent. With a key, LangChain `create_agent` calls the configured OpenAI model and can use a read-only `list_study_tasks` tool. MCP SDK exposes that task tool as an independent stdio server; connecting LangChain to MCP transport is a later integration step. RAG remains an interface.
