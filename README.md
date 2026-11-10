# DecisionGateway

One HTTP contract for decision-type models, on port **29406**. Callers name a saved gateway and send typed questions. TypeSafe Jev, Ollama or a Scuti model service answers them. DecisionGateway holds no model. Its FastMCP shell exposes no tools.

## API

With an admin password configured, `/api/*` requires a caller token in `X-Internal-Token`. `X-Requester-Username` optionally labels usage; it defaults to `unknown`.

| Method and route | Request | Response |
|---|---|---|
| `POST /api/decide` | Fields below | `{gateway, model, answers, tokens, streamed}` or NDJSON |
| `GET /api/gateways` | None | `{gateways: [...]}` with public entries, `streams`, `images`, `types`, `reachable` |
| `POST /api/validate` | `{questions}` | `{ok: true}` or 422 |
| `GET /health` | No token | `{ok: true, ready: boolean}`; ready means at least one gateway is saved |

| Decide field | Rule |
|---|---|
| `gateway` | Required saved gateway id |
| `text` | Required non-empty string, at most 16,000 characters by default |
| `questions` | Object of 1–8 named questions; see types below |
| `assets` | Optional non-empty object of referenced images |
| `min_confidence` | Optional number greater than 0 and at most 1 |
| `trace` | Optional boolean, default false; preserves gateway trace details |
| `stream` | Optional boolean, default false; returns NDJSON when true |

Unknown decide fields return 422. Each question has `type` and non-empty `instructions`. `choice` requires `criteria` with 2–10 option-to-description strings. `score` requires 2–10 level descriptions, lowest first; its value is between 0 and the last level index. `noul` accepts no criteria or exactly `false` and `true` labels. `box` takes no criteria and needs an image in `assets`.

Answers contain `type`, the corresponding `choice`, `score`, `noul` or `box` value, `answer_confidence`, `uncertain` and `answered_by` (gateway id). Native choice answers include `probabilities`; native score answers include `legend`. Scuti answers preserve the model service's answer fields. `tokens` counts input tokens; Scuti sums `input_tokens` over `calls`.

**Images.** Send `{placeholder: {type: "image", format: "png" or "jpg" or "jpeg", data_base64: "..."}}` in `assets`. Use standard padded base64 without a `data:` prefix. Each decoded image is at most 16 MiB; the entire request body is at most 32 MiB. Every placeholder must appear in text or a question. Name the image in box instructions. TypeSafe receives only assets referenced by each question or the shared text, with `TypeSafe-Danger-Zone-Images: true`. An image is billed again for every question that uses it; an image in shared text is sent once per question. TypeSafe also enforces image dimensions and format restrictions upstream.

**Box answers.** `box` contains `top`, `bottom`, `left`, `right`, as fractions in `[0,1]`. Top/bottom are measured from the top edge; left/right from the left edge. Each first edge precedes the second. With no upstream confidence, `answer_confidence` is `null`: `uncertain` is true only when the caller supplied `min_confidence`. Use a Jev model that supports box questions.

**Confidence.** Caller `min_confidence` overrides gateway defaults. TypeSafe defaults to 0.9. Ollama defaults to 0.9 for two options/levels or noul, otherwise 0.75. Noul confidence is `max(noul, 1 - noul)`. Scuti keeps its own threshold behavior. Without `trace`, `rounds`, `voters`, `options`, `disagreement`, `resolved_by` and `eliminated` are removed.

**Streaming.** `stream: true` returns `application/x-ndjson`: one `{"type":"answer","id":"q","answer":{...}}` per answer, then `{"type":"done", ...}` containing the full response. Scuti streams natively (`streamed: true`); other kinds and cache hits emit the same lines after completing (`streamed: false`). Failures before the first line are HTTP errors. Later failures end with `{"type":"error","status":502,"detail":"..."}`.

**Cache.** Answers are cached in memory for 300 seconds, up to 500 entries by default. The key includes gateway id, text, questions, asset-content hashes, `min_confidence` and `trace`; `stream` is excluded. Change cache settings on the admin page. Restart clears the cache.

Rebuilding an adapter after a saved gateway change clears cached answers so the new model/address is used. A truncated upstream stream produces a clean error instead of silently ending.

### Gateways

Save entries at `/admin/gateways.html`; addresses and upstream credentials have no environment variables. All kinds accept unique `id` (`[a-z0-9][a-z0-9_-]{0,47}`) and integer `timeout_s` (1–600, default 60).

| Kind | Fields | Images | Box | Native streaming |
|---|---|---|---|---|
| `typesafe` | `url` (default TypeSafe `/v1/systemone`), required `model`, required `api_key` on create | Yes | Yes | No |
| `ollama` | Required `url`, `model` | No | No | No |
| `scuti` | Required `url`; optional `token`, `strategy`, `window` (16–8192, sent as `max_len`) | No | No | Yes |

All kinds answer choice, score and noul. Scuti calls `DSC_Laya_Model` or `DSC_D3_Model` at `/v1/ask`. Ollama uses `/v1/systemone`, and must have the requested decision model installed. TypeSafe uses native question types and makes one concurrent call per question. Scuti plain requests retry 429 twice, honoring `Retry-After` up to 10 seconds. Secrets are write-only; public entries use `has_api_key` / `has_token` flags. Omitting a secret when editing preserves it.

### Errors and limits

Decide errors are `{error, message}`; admin errors use `detail`. Messages omit upstream bodies and credentials.

| Status | Meaning |
|---|---|
| 401 | Missing, revoked, expired or incorrect caller token; admin routes require their separate password |
| 413 | Request exceeds body limit or upstream refuses its size |
| 422 | Invalid request, unknown gateway, unsupported capability or upstream request refusal |
| 429 | Caller token rate exceeded, or in-flight decisions full; inspect `Retry-After` |
| 502 | Unreachable gateway, refused upstream credentials or unusable reply |
| 503 | Model unavailable/not ready, or upstream busy |

The default in-flight limit is 8. Token calls-per-minute limits are configured per caller on **Access tokens**. Unsupported images or question types are rejected before calling a gateway.

## Setup

1. Install dependencies with `uv sync`; on Windows set `UV_CACHE_DIR=D:/User/.uv-cache` and `UV_LINK_MODE=copy` first.
2. Copy `.env.example` to `.env` and set `SERVICE_ADMIN_PASSWORD` locally.
3. Start with `run.bat run`, or follow a [deployment guide](deployment.md).
4. Open `/admin/`, sign in and create a caller token under **Access tokens**.
5. Open `/admin/gateways.html`, enter the admin password, save a gateway and press **Test**. Save gateway connections on this page before making decisions.

## Admin page

The shared page provides Overview, Access tokens, Runtime & settings, Usage and Connect & API. Model connections has no fixed gateway slots. Manage gateways on the separate page linked from Connect & API. No service-specific Playground operation is registered. See [the web UI guide](docs/guide-web-ui.md).

## Settings and environment

Startup settings are listed in [Docker settings](docs/guide-docker-same-device.md#settings). Limits, answer cache, data folder and gateways are managed on admin pages. Saved options override environment defaults. With no admin password, admin pages and token checks are disabled; the server permits only a loopback bind.

## Limits worth knowing

`/health` readiness means a saved gateway exists, not that it is reachable. `/api/gateways` probes reachability concurrently with a 3-second limit and keeps results for 15 seconds. Gateway Test explicitly probes again. TypeSafe native score/noul behavior has been verified with mocked transports only. Docker image build and real upstream inference have not been verified in this implementation run.

## Tests

```bash
uv run pytest -q
uv run python tools/check_sync.py
```

Tests use `httpx.MockTransport`; no real API keys or upstream network calls. The local-server smoke test checks health, gateway save and the gateways page.

## Try it from the admin page

Create a caller token on `/admin/` and a gateway on `/admin/gateways.html`. Use the public HTTP API below; the empty FastMCP shell has no decision tools or configured Playground operation. Replace token placeholders locally.

```bash
curl -X POST http://127.0.0.1:29406/api/decide -H "X-Internal-Token: <SERVICE_TOKEN>" -H "Content-Type: application/json" -d '{"gateway":"jev","text":"card charged twice","questions":{"team":{"type":"choice","instructions":"Which team?","criteria":{"billing":"Invoices","returns":"Refunds"}}}}'
```

For an image box question, replace `<PADDED_PNG_BASE64>` with image bytes encoded as standard base64:

```bash
curl -X POST http://127.0.0.1:29406/api/decide -H "X-Internal-Token: <SERVICE_TOKEN>" -H "Content-Type: application/json" -d '{"gateway":"jev","text":"Inspect photo1","questions":{"where":{"type":"box","instructions":"Locate the red rectangle in photo1"}},"assets":{"photo1":{"type":"image","format":"png","data_base64":"<PADDED_PNG_BASE64>"}},"min_confidence":0.8}'
```

For native streaming through a saved Scuti gateway:

```bash
curl -N -X POST http://127.0.0.1:29406/api/decide -H "X-Internal-Token: <SERVICE_TOKEN>" -H "Content-Type: application/json" -d '{"gateway":"laya","text":"card charged twice","questions":{"billing":{"type":"noul","instructions":"Is this about billing?"}},"stream":true}'
```

## Connect

Containers on `citadel_core` call `http://decisiongateway:29406`; decide is `POST /api/decide`. Native callers use `http://127.0.0.1:29406`. A container reaching a model on its host uses `host.docker.internal`, not its own loopback address. Configure gateway URLs as reachable from DecisionGateway's runtime.

## Documentation

- [Purpose](docs/purpose.md)
- [Deployment](deployment.md)
- [Changelog](CHANGELOG.md)
- [Admin web UI](docs/guide-web-ui.md)
- [Docker on this PC](docs/guide-docker-same-device.md)
- [Docker on another machine](docs/guide-docker-deployment-device.md)
- [Run without Docker](docs/guide-no-docker-same-device.md)
- [Approved design](docs/superpowers/specs/2026-11-10-decision-gateway-design.md)
- [Approved implementation plan](docs/superpowers/plans/2026-11-10-decision-gateway.md)
