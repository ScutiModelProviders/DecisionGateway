# DecisionGateway: the admin web UI

Set `SERVICE_ADMIN_PASSWORD`, then open `http://127.0.0.1:29406/admin/` and sign in. Admin authentication uses `X-Admin-Password`; public requests use caller tokens.

## Navigation

The shared sidebar supports theme and collapsed navigation preferences. Gateways use a separate page, `/admin/gateways.html`, listed under Connect & API.

| Page | Behavior |
|---|---|
| Overview | Saved gateway ids and kinds; health readiness means at least one saved gateway |
| Playground | No DecisionGateway operation is registered; use the README's HTTP examples |
| Access tokens | Create, expire, rate-limit and revoke caller tokens |
| Model connections | No fixed slots; decisions use the separate Gateways page |
| Runtime & settings | Save options and reset values to defaults |
| Usage | Calls, errors and average time per requester, reset on restart |
| Connect & API | Addresses, endpoints and the gateway admin-page path |

## Access tokens

Create one token per caller. Copy the newly issued token directly into the caller's private configuration; it is shown only once. Supply it as `X-Internal-Token`. Optional calls-per-minute and expiry restrict it; revoke disables it immediately. Stored tokens are hashed. `/health` needs no token. Admin routes check the separate admin password.

## Gateways

Open `/admin/gateways.html`, enter the admin password and press **Load gateways**. The table shows id, kind, model/address, streams, images, supported question types and reachability. **Edit** loads an entry into the form; **Delete** requests confirmation; **Test** probes connectivity.

| Fields | Meaning |
|---|---|
| Id, Kind, Timeout | Unique lowercase id; `typesafe`, `ollama` or `scuti`; timeout 1–600 seconds |
| TypeSafe | Optional address, required model and API key on first save |
| Ollama | Required address and installed decision-model name |
| Scuti | Required model-service address; optional token, strategy and window 16–8192 |

Secret inputs use password fields. Saved secrets are never returned; a saved hint appears instead. Leave a saved secret empty to retain it. Errors appear in the page's live status region. Credentials entered here are for the upstream gateway; caller tokens belong on the shared Access tokens page. The password field stays in memory on the gateway page.

TypeSafe Test uses `/v1/models`, Ollama Test uses `/api/show`, and Scuti Test uses `/health`. A successful test checks connectivity/readiness, not inference for every question type. TypeSafe accepts images and box; Ollama and Scuti reject them. Only Scuti streams natively.

## Runtime & settings and Usage

Saved values override environment defaults; reset removes the saved override. These options apply live:

| Setting | Default | Range |
|---|---|---|
| Longest text | 16000 characters | 1–100000 |
| Decisions at once | 8 | 1–256; excess returns 429 with `Retry-After` |
| Keep answers (cache) | On | On/off |
| Keep cached answers for | 300 seconds | 1–86400 |
| Cached answers kept | 500 | 1–100000 |

**Data folder** applies after restart. Settings, gateways and caller tokens remain in the original state folder. Existing files are not moved. Usage counts one entry per decide request; later stream lines do not create additional entries. `X-Requester-Username` labels usage and defaults to `unknown`.

## Connect & API

Copy the appropriate address for native clients, Docker containers or another machine. Containers sharing `citadel_core` use `http://decisiongateway:29406`. `/mcp` is an empty shell: it has no decision tools. Use `/api/decide`, `/api/gateways` and `/api/validate`.

## Try it: this service's request

Save and Test a gateway, create a caller token, then use a [README curl example](../README.md#try-it-from-the-admin-page). The choice example accepts typed options; the image example requires a TypeSafe gateway and valid base64; the streaming example emits NDJSON.

## Problems

An empty gateway list needs a saved entry. A 401 on public routes needs a valid caller token; a 401 on admin routes needs the admin password. Inspect gateway Test for reachability and model readiness. See [deployment problems](guide-docker-same-device.md#problems).
