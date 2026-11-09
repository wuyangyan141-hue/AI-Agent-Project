# AI Learning Companion · desktop pet

A graduate team project scaffold for an extensible desktop study companion. Electron owns the window, React + TypeScript renders chat/tasks/settings and a state-driven pet placeholder, FastAPI owns REST/WebSocket endpoints, and SQLite stores local conversations, tasks and preferences.

## Run locally

Requires Node.js 20+ (CI: 22), npm and Python 3.12. In one terminal:

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from repository root:

```bash
npm ci
npm run dev
```

Send a chat message, add a task and change the pet name. Data is stored at `services/api/data/companion.db` relative to the backend working directory. No API key is required for the deterministic demo. To enable a real LangChain agent, set `OPENAI_API_KEY` in the backend process environment and optionally `AGENT_MODEL` (default `openai:gpt-4o-mini`). Never commit keys. For custom frontend URLs create `apps/desktop/.env.local` with `VITE_WS_URL` and `VITE_API_URL`.

## Verify

```bash
npm run typecheck && npm test && npm run build
cd services/api && python -m pytest -q
```

## Team modules

| Location | Responsibility / next implementation |
|---|---|
| `apps/desktop/electron` | Secure window shell; transparent always-on-top pet window and drag behavior later |
| `apps/desktop/src` | Chat, tasks, settings and pet event mapping; replace emoji with sprite animation later |
| `services/api/app/agent` | LangChain `create_agent` with prompt and read-only task tool; richer planning later |
| `services/api/app/rag` | Retriever contract; document ingestion, indexing and citation later |
| `services/api/app/mcp` | MCP Python SDK stdio tool server and registry contract; agent-to-MCP transport adapter later |
| `services/api/app/skills` | Reusable workflow contract; validated workflows later |
| `services/api/app/database` | SQLite tables and small repository; migrations and multi-session isolation later |
| `docs` | [API contract](docs/api.md) and [development guide](docs/development.md) |

LangChain is optional at run time; with no key, the app clearly reports demo mode. MCP tool exposure is real but the current Agent uses its equivalent local read-only tool directly. The desktop UI is an application window, not yet a transparent floating pet. Use LangGraph when explicit multi-step state, approvals and retries become necessary. Bind the backend to loopback; add authentication and stricter origin policy before remote access or packaging for distribution.
