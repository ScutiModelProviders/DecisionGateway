# DecisionGateway design

Date: 2026-11-10. Status: approved in chat, waiting for spec review.

## Purpose

DecisionGateway is a tool service (`AI/ToolServices/DecisionGateway`, port 29406). It gives callers one HTTP contract for decision-type models. Callers send typed questions and name a gateway. The service sends them to that gateway and returns answers in one shape.

It takes the decision part of Legion's `providers/decision` (`contract.py`, `questions.py`, the gateways). It leaves out the harness: no chat or agent loop, no `run_chat`, no `agent_spec`, no tools or history. It also leaves out strategies and escalation; the caller picks the gateway.

## Placement and parity

- Python, FastAPI, uv. Same layout as Mimic and Bard.
- Copies the shared admin files unchanged: `web/index.html`, `web/playground.js`, `src/admin_api.py`, `src/tokens.py`, `src/middleware.py`, `src/runtime.py`, `tests/test_admin_api.py`, `tests/test_tokens.py`, `tests/seed.py`, `tools/check_sync.py`. These are byte-identical in five tool services today. `check_sync.py` must cover six after this change, and the new service is added to each sibling's list.
- Updates `AI/ToolServices/_docs/`: `GUIDES.md`, `HARDWARE.md`, `PURPOSES.md` (group: Decision), `SERVICE-SPECIFIC.md` (port 29406 and every difference).
- Follows the `tool-service-parity`, `service-docs`, `service-groups` and `service-layout` skills. Ships `AGENTS.md`, `CLAUDE.md` (imports `@AGENTS.md`), `README.md`, `deployment.md`, `docs/purpose.md`, the four `docs/guide-*.md`, `.env.example`, `CHANGELOG.md`, `VERSION`, Docker files and `tools/publish_live.py`.
- Brain note `Brain/Projects/DecisionGateway.md` through the `project-sync` skill, after the code exists.

## API

All routes except `/health` need `X-Internal-Token` when `SERVICE_ADMIN_PASSWORD` is set. Admin routes are guarded by the admin password, as in the other tool services.

### `POST /api/decide`

Request:

| Field | Rule |
|---|---|
| `gateway` | Required. Id of a configured gateway. |
| `text` | Required, non-empty, at most 16,000 characters. |
| `questions` | Required object, 1 to 8 questions. Each is `{type, instructions, criteria}` with `type` one of `choice`, `score`, `noul`, `box`. Validation is Legion's `parse_request` rules (choice: object of option descriptions; score: non-empty list of level descriptions; noul: `false` and `true` labels, or no `criteria`). `box` takes only `type` and `instructions`; `criteria` is refused. A `box` question needs at least one entry in `assets`, and its `instructions` name the image by placeholder (for example "Locate the red rectangle in `photo`"). |
| `assets` | Optional object of images, same shape as TypeSafe's: `{placeholder: {type: "image", format: "png"\|"jpg"\|"jpeg", data_base64}}`. The placeholder is an opaque key (a UUID is recommended) that the caller writes into `text`, a question's `instructions` or its `criteria` where the image is used. Rules: at least one asset when the field is present; `data_base64` is standard base64 with padding and no `data:` prefix; each decoded image is at most 16 MiB; the whole request body is at most 32 MiB; every asset is referenced somewhere, or 422. Only gateways with `images: true` accept it (see Gateways). |
| `min_confidence` | Optional, above 0 and at most 1. Sets `uncertain` per answer. A gateway with its own thresholds uses them when it is absent. |
| `trace` | Optional boolean. Adds gateway trace detail (`rounds`, `voters`, `options`, ...). Without it these keys are removed. |
| `stream` | Optional boolean. See Streaming. |

Unknown fields return 422.

Response: `{gateway, model, answers, tokens, streamed}`. Each answer has `type`, the pick (`choice`, `score`, `noul` or `box`), `answer_confidence`, `uncertain` and `answered_by` (the gateway id). A `box` answer carries `box: {top, bottom, left, right}`, fractions from 0 to 1 of the image (top and bottom from the top edge, left and right from the left edge). Its `answer_confidence` is `null` when Jev gives none; then `uncertain` is `true` only if the caller set `min_confidence` (the bar cannot be checked), otherwise `false`. `choice` and `score` answers carry `probabilities` and `legend` as the Laya shape does. `tokens` is input tokens.

### Streaming

With `stream: true` the reply is `application/x-ndjson`: one `{"type":"answer","id","answer"}` line per question, then `{"type":"done", ...}` with the same body a non-stream call returns. A gateway that can stream is streamed. A gateway that cannot is emulated: the service gets the full answer, then sends the same lines. `streamed` in the `done` body says whether lines arrived early. A failure before the first line is a normal HTTP error. A failure after it is `{"type":"error","status","detail"}` and ends the stream.

### Other routes

- `GET /api/gateways`: configured ids with `kind`, `model`, `reachable`, `streams`, `images` and `types`. No secrets. The admin Gateways card shows the same flags.
- `POST /api/validate`: `{"questions"}` returns `{"ok": true}` or 422 saying what is wrong.
- `GET /health`: `status`, `ready` (at least one gateway reachable), gateway count. No token.
- Admin: `/admin/` page with a Gateways card (add, edit, delete, test), the shared Tokens and Settings cards, and the answer cache switch.

### Errors

422 bad request or unknown gateway. 401 and 429 from the shared middleware. 429 with `Retry-After` when `max_inflight` is full. 502 when the gateway answered unusably or could not be reached. 503 when the gateway is configured but not ready (for example d3 weights not downloaded). Messages never contain paths, URLs, credentials or upstream bodies.

## Gateways

Config is a list of entries in `backends.json` in the state folder, edited only on the admin page. Secret fields (`api_key`, `token`) are write-only and never returned or logged. There are no environment variables for addresses or secrets.

Common fields: `id` (unique, `^[a-z0-9][a-z0-9_-]{0,47}$`), `kind`, `timeout_s`. Examples of ids: `jev`, `d3`, `laya`.

Each kind is one adapter file behind one protocol:

```python
class DecisionGateway(Protocol):
    id: str
    kind: str
    streams: bool
    types: frozenset[str]   # question types it answers; a request with any other type gets 422 and the gateway is never called
    images: bool   # accepts `assets`; a request with assets for a gateway where this is False gets 422, never a silent drop
    def available(self) -> bool: ...
    async def ask(self, request: DecisionRequest, timeout: float | None) -> GatewayResult: ...
```

All adapters use async httpx. A new kind is one adapter plus one registry entry.

### `typesafe`

TypeSafe's Jev API (`POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer`). Fields: `url`, `api_key`, `model` (for example `jev-latest`). `images: true`. Does not stream.

- `types`: `choice`, `score`, `noul`, `box`.
- Box: sent natively (`{"type": "box", "instructions": ...}`); the reply `box` object and nullable `confidence` map as described under Response. Box needs Jev 1.14, so the gateway's `model` must resolve to it (`jev-latest` and `jev-preview` do today; a pinned `jev-1.13.0` makes TypeSafe refuse). The adapter sends the same image header as for any image. If TypeSafe refuses a box question, the caller gets a clean 422 or 502 that says the model may not support box questions, with no upstream body.
- Questions: the API supports `choice`, `score` and `noul` natively, so the adapter sends each question as its own type and maps the reply to the shared shape. Noul has no confidence in the API; `answer_confidence` is `max(noul, 1 - noul)`, the same rule as DSC_D3_Model. Legion's `jev.py` instead turned score and noul into choices; the new adapter drops that workaround. Confirm this against the live API in the first test run; if a native type misbehaves, fall back to Legion's mapping for that type.
- One call per question, as in Legion. Each call carries `assets`, and every use of a placeholder bills the image again, so an image in `text` is billed once per question. The README says so.
- Images: the adapter sends `assets` as given (base64 JSON) and adds the header `TypeSafe-Danger-Zone-Images: true`, which the API requires for any request with an image. TypeSafe itself checks size and pixels (280 to 1568 px per side, 78,400 to 2,458,624 pixels, PNG or JPEG only, no animation). Its 400 and 413 replies become a 422 or 413 with a clean message and no upstream body.
- Default `min_confidence` when the request has none: 0.9.

### `ollama`

An Ollama decision model, such as d3, through Ollama's `/v1/systemone`. Fields: `url`, `model`. `images: false` for now: `DSC_D3_Model` itself passes text only, and this service has no verified image format for Ollama. The flag is one line to change when that is verified. It maps Ollama's raw result (pick, probabilities, confidence) to the shared answer shape using the same rules as `DSC_D3_Model/src/answers.py`. For `noul`, `answer_confidence` is `max(noul, 1 - noul)`, the same rule as DSC_D3_Model. Does not stream.

### `scuti`

A `DSC_*` model service. `images: false`: Laya cannot read images and `DSC_D3_Model` refuses `images` with 422. Both existing ones (`DSC_Laya_Model`, `DSC_D3_Model`) expose the Laya-shaped `POST /v1/ask`, so one adapter serves both. Fields: `url`, `token`, optional `strategy` (sent as `strategy`; the service default applies when empty), optional `window` (sent as `max_len`, Laya only). `min_confidence` and `trace` pass through. It streams by passing `stream: true` to the model service and relaying its NDJSON. It retries a 429 up to twice, waiting `Retry-After` (at most 10 seconds), as Legion's `laya_model.py` does. `calls` from the model service are summed into `tokens`.

## Cache and limits

- Answer cache, keyed by gateway id, text, questions and options that change the answer (`min_confidence`, `trace`) and a hash of each asset. `stream` is not in the key. Switchable on the admin page. Same behavior as the model services.
- `max_inflight` cap and per-token calls-per-minute from the shared middleware.

## Out of scope

Strategies, escalation chains, `local_only`, MCP endpoint, free-form text generation, training or checkpoint handling. Also out for now: multipart image upload and image URLs (TypeSafe takes base64 or multipart only), and compression of the upstream request.

## Testing

`uv run pytest -q`, using fake httpx transports and injected fakes only. No real network.

- Request validation: every rule above, unknown fields, size limits.
- Per-kind mapping: `typesafe` choice, score and noul; `ollama` mapping; `scuti` for a Laya-shaped and a d3-shaped reply.
- Box: validation (no `criteria`, needs `assets`); a `box` question to a gateway whose `types` lacks `box` gets 422 and no call; `typesafe` sends the native box question and maps `box` and a `null` confidence (the `uncertain` rule above); a TypeSafe refusal becomes a clean error.
- Images: `assets` validation (format, base64, size, unreferenced asset, missing placeholder); a request with `assets` to a gateway with `images: false` gets 422 and the gateway is never called; `typesafe` sends `assets` and the `TypeSafe-Danger-Zone-Images: true` header (checked on the fake transport); TypeSafe 400 and 413 map to clean errors; the cache key changes with the image.
- Streaming: native relay, emulation, error before and after the first line.
- Unknown, unreachable and not-ready gateways give the right status and a clean message.
- Tokens, 401, 429 and `max_inflight`, from the shared tests.
- Secrets never appear in any response, log line or `GET /api/gateways`.
- `tools/check_sync.py` exits 0 in all six services.

## Decisions taken in design

- Service, not library: one contract for all callers, secrets in one place, shared cache and limits.
- Caller names the gateway: no strategy logic in the service.
- Config-driven gateway instances: new Ollama models or Scuti services need no code.
- Kind names follow the vendor or runtime (`typesafe`, `ollama`, `scuti`), not the model name (`jev`).
- Streaming is always accepted; a gateway that cannot stream is emulated.
- Full tool-service parity, including admin page and cache.

## Adjustments found while planning (approved: own gateways page)

- **Routes under `/api/`.** The shared `src/middleware.py` guards only `/mcp` and `/api/*`, and it must stay byte-identical. So the HTTP routes are `/api/decide`, `/api/gateways` and `/api/validate`, not `/v1/...`. Upstream calls to TypeSafe, Ollama and the model services keep their own `/v1/...` paths.
- **Gateways page.** The shared admin page only edits fixed slots (one URL and token each). Gateways are a dynamic list, so DecisionGateway adds its own `web/gateways.html` (served at `/admin/gateways.html`) and the routes `GET/PUT/DELETE /admin/gateways[/{id}]` and `POST /admin/gateways/{id}/test`, guarded by `X-Admin-Password`. The shared files stay untouched; the shared page's Model connections section shows no slots. The deviation is recorded in `SERVICE-SPECIFIC.md`. The `connect` descriptor lists the gateways page and the API routes.
- **MCP shell.** `register(...)` in the shared `admin_api.py` takes a `FastMCP` object only to attach routes (`mcp.custom_route`). DecisionGateway builds a `FastMCP` with no tools and serves the same Starlette app; `/mcp` exists but lists no tools.
- **Storage.** Gateways live in `gateways.json` in the state folder. Secret fields are write-only. `backends.json` stays empty.
