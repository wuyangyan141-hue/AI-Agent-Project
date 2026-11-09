# Team development

- `main` receives reviewed PRs. Create focused branches (`feat/...`, `fix/...`, `docs/...`), link an issue and request teammate review.
- Run `npm run typecheck && npm test && npm run build` and `cd services/api && python -m pytest -q` before opening a PR.
- Keep Electron main/preload/renderer isolated. Never enable renderer Node integration. Bind local backend to loopback during development.
- Store secrets in ignored local env files; commit only examples. Avoid putting document content or credentials in logs.
- Add tests for new API behavior and update `docs/api.md` whenever the event schema changes.
- Module owners can implement `Agent`, `Retriever`, `ToolRegistry`, `Skill` interfaces independently. SQLite schema changes should be migrations and reviewed with API changes.
