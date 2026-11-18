# Changelog

## Unreleased

### Gateways in the sidebar

The sidebar item that was called Model connections is now Gateways and shows the gateway list and editor inside the admin page. `/admin/gateways.html` still works on its own. The admin page and `tools/check_sync.py` now stay in step with ConversationGateway only, not with the tool services.

### Service workspace

Admin now opens to a full-width Overview with live readiness, request activity by requester, service details and caller tokens. Use the tabs below the service name for Playground, settings, connections and access management.

### Copy works on plain http and inside a frame

The Copy buttons for a new token and for the addresses now fall back to a hidden text box when the browser refuses the clipboard API (plain http pages, framed pages such as ServiceHub). It is the same fallback the model services already had.

### Playground works behind a path-prefix proxy

The Try it panel built its request URLs from the page origin, so behind ServiceHub (`/s/<id>/`) it called the hub's root and got 404 Not Found. It now resolves routes against the service root (`../` from the admin page). Same-origin checking is unchanged.

## 1.0.0

- Admin sign-in loads live settings; gateway changes clear stale answers; incomplete upstream streams return clean errors.
- One HTTP contract for choice, score, noul and image box decisions.
- TypeSafe Jev, Ollama decision models and Scuti DSC model-service gateways.
- Gateway administration with write-only secrets, capability flags and connectivity tests.
- Native and emulated NDJSON streaming, answer cache and in-flight limit.
- Shared admin page, runtime settings, caller tokens, rate limits and usage.
- Docker and native Windows launchers on port 29406.
