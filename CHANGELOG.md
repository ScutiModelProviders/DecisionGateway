# Changelog

## Unreleased

### Test gives up after 20 seconds and shows it is working

A Test against an address that never answered waited for the gateway's whole timeout (300 seconds by default) and showed nothing, so the button seemed dead. Test now stops after 20 seconds with "No answer within 20 seconds". While it waits, the button spins, the row breathes and the message counts the seconds; the result flashes the button green or red.

### Test shows its result where you can see it

The message of Test, Save and Delete sat under the long form, so pressing Test seemed to do nothing. It now sits above the table, scrolls into view, and Test shows "Testing…" while it waits.

### Usual addresses and a model-name link on the Gateways page

A new gateway starts from the usual address of its kind (TypeSafe's API, Ollama on `127.0.0.1:11434`, a Scuti model service on `127.0.0.1:29220`); change it when the service runs elsewhere. An Ollama gateway shows a link to the model names on ollama.com.

### Icon buttons on the Gateways page

The actions of a saved gateway (Test, Edit, Delete, and Models where a preset has a model list) are square icon buttons of one size, each with a tooltip and a screen-reader name.

### Neutral dark theme

The admin page's dark theme uses the neutral dark palette with the orange accent again, in place of the blue-navy one from the tabbed redesign. The light theme is unchanged.

### Gateways tab matches the other tabs

The Gateways editor now uses the admin page's colors, type, tables, buttons and form card, and follows the Theme toggle.

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
