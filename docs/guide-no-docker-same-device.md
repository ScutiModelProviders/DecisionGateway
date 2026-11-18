# DecisionGateway: without Docker, on Windows

Run one process on `127.0.0.1:29406`.

## Requirements

- Python 3.11+ managed by uv; install uv with `winget install astral-sh.uv` if needed.
- A reachable TypeSafe, Ollama or Scuti decision gateway. No model or ffmpeg runs in DecisionGateway.

## Start

In PowerShell, from the project folder:

```powershell
$env:UV_CACHE_DIR = "D:/User/.uv-cache"
$env:UV_LINK_MODE = "copy"
uv sync
```

Copy `.env.example` to `.env` and set `SERVICE_ADMIN_PASSWORD` locally. See [Settings](guide-docker-same-device.md#settings). Start through the menu's Run option or:

```powershell
./run.bat run
```

The launcher loads startup settings through `--dotenv`; real environment variables win. For the equivalent direct entry point:

```powershell
uv run python -m src.run --dotenv
```

Without `--dotenv`, it uses the process environment only.

## Check

```bash
curl http://127.0.0.1:29406/health
```

First run: set the admin password, sign in to `/admin/`, make a caller token, save a gateway at `/admin/gateways.html` and press **Test**. The local smoke test passed health, gateway save and page loading; upstream inference was not exercised.

## Stop

Press Ctrl+C in the terminal. Docker and native runs cannot share port 29406.

## Tests

Keep both Windows uv variables set, then run:

```bash
uv run pytest -q
uv run python tools/check_sync.py
```

Tests use fake transports, with no upstream API calls or real credentials.

## Problems

See [Problems](guide-docker-same-device.md#problems).
