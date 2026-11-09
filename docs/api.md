# API contract (v0.1)

Base URL `http://127.0.0.1:8000`; FastAPI interactive OpenAPI: `/docs`.

- `GET /health` → `200 {"status":"ok"}`.
- `WS /ws/chat` → server immediately sends `{"type":"welcome","text":"..."}`.
- Client sends `{"type":"message","text":"复习数据库"}`. Server replies `{"type":"reply","text":"..."}`.
- Invalid events receive `{"type":"error","text":"..."}`. The socket stays open; disconnect ends the session.

The current response is a deterministic echo prototype. No LLM, retrieval, tool execution or persistence is enabled yet. Event types are validated on both sides. Keep future events versioned and documented here.
