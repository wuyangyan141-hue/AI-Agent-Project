# Team development

- `main` receives reviewed PRs. Create focused branches (`feat/...`, `fix/...`, `docs/...`); link an issue and request review.
- Run `npm run typecheck && npm test && npm run build` and `cd services/api && python -m pytest -q` before a PR.
- Electron main/preload/renderer stay isolated. Do not enable renderer Node integration. Keep the backend on loopback for development.
- Store keys in ignored local files or the process environment. Do not commit keys, user documents or the SQLite database.
- Update `docs/api.md` when event schemas or REST endpoints change. Add behavior tests to the relevant module.
- Suggested division: desktop shell/pet; React UX; backend LangChain/MCP; RAG/SQLite/evaluation. Agree on API contracts in a PR before integrating modules.
- Treat `rag`, `skills` and MCP client integration as interface work until each module has a runnable test. Do not describe reserved events as implemented execution.
