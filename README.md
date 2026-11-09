# AI Learning Companion · desktop pet

Graduate course team project: an extensible AI study companion with an Electron desktop pet and React chat. The first milestone runs a FastAPI WebSocket echo service and a desktop client. The whale is an interaction placeholder; LLM responses, task management and animated pet behavior are future milestones.

## Requirements

Node.js 20+ (CI uses 22), npm, Python 3.12. Start backend and desktop in separate terminals:

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
npm ci
npm run dev
```

Send a message in the desktop window; it should show `收到：…`. For a browser-only renderer preview run `npm run dev -w @companion/desktop -- --help` to see the Electron command, or `npm exec -w @companion/desktop vite -- --host 127.0.0.1`. Use `apps/desktop/.env.local` with `VITE_WS_URL=ws://127.0.0.1:8000/ws/chat` if the backend address changes. The backend currently accepts local development connections; add explicit origin and authentication policy before distribution.

## Validate

```bash
npm run typecheck && npm test && npm run build
cd services/api && python -m pytest -q
```

## Layout

- `apps/desktop/electron`: secure desktop shell and preload boundary.
- `apps/desktop/src`: React renderer, chat and WebSocket protocol.
- `services/api/app/agent`: LangChain integration seam; echo implementation for first milestone.
- `services/api/app/rag`: local retrieval interface with source attribution.
- `services/api/app/mcp`: MCP Python SDK tool registry interface.
- `services/api/app/skills`: reusable workflow interface.
- `services/api/app/database`: SQLite connection factory (schema follows).
- `docs/api.md`: message contract; `docs/development.md`: collaboration rules.

Dependencies for LangChain and MCP are installed but intentionally not used by the echo prototype. See [API contract](docs/api.md) and [team development](docs/development.md).
