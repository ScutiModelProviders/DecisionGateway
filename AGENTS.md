# DecisionGateway

HTTP service on port 29406 for typed decisions through gateways of kind `typesafe`, `ollama` and `scuti`. Holds no model. FastMCP supplies an empty shell with no MCP tools; callers use `/api/decide`, `/api/gateways` and `/api/validate`. Environment prefix `SERVICE_`; caller token prefix `dg_`.

## Agent instructions

Edit `AGENTS.md`; `CLAUDE.md` only imports it through `@AGENTS.md`.

## Commands

- Install: `uv sync`. On Windows set `UV_CACHE_DIR=D:/User/.uv-cache` and `UV_LINK_MODE=copy` for every uv command.
- Test: `uv run pytest -q`; shared parity: `uv run python tools/check_sync.py`.
- Run: `run.bat run`, or `uv run python -m src.run`; add `--dotenv` to load local startup values.

## Rules

- When changing this service, follow `tool-service-parity`, `service-layout`, `service-docs` and `service-groups`; shared group rules live in `AI/ToolServices/_docs/`.
- Never read or print `.env`, `.env.local`, `gateways.json`, `tokens.json` or `settings.json`. Secrets `api_key` and `token` are write-only in responses, logs and errors.
- Keep domain logic in `service.py`, `contract.py` and `gateways/`; `app.py` is transport glue. Run blocking file operations through `asyncio.to_thread`.
- Gateway entries live in `Settings.state_dir / "gateways.json"`, edited through `/admin/gateways.html`. Saved Data folder moves stored data on restart while settings, gateways and tokens stay in the first folder.
- Use `httpx.MockTransport` for tests; no real network or API keys.
- Keep `src/admin_api.py`, `src/tokens.py`, `src/middleware.py`, `src/runtime.py`, `web/index.html`, `web/playground.js`, `tests/test_admin_api.py`, `tests/test_tokens.py`, `tests/seed.py`, `tests/test_env_file.py` and `tools/check_sync.py` byte-identical to Bard. If a copied test fails, stop and report. `tools/check_sync.py` must exit 0.
- Author commits with email `214214011+scutiii2@users.noreply.github.com` and name from `git -C ../Bard config user.name`. End messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Update docs with behavior changes. Current approved implementation separates project files (Task 10) from service docs (Task 12).
- Current authorization excludes Task 11 and all sibling/shared edits. Only Task 12's vault note through `project-sync` is authorized outside this project. Do not push, add a remote or run `tools/publish_live.py`.
