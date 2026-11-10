# DecisionGateway: Docker on a deployment machine

Callers use the machine's published port 29406 or `http://decisiongateway:29406` on `citadel_core`. Deployment has not been run in this implementation session.

## Requirements

- Docker with Compose v2, `citadel_core` and a reachable decision gateway.
- Access to copy the project to the deployment machine.
- For future publishing: a configured repository remote and an explicitly authorized release workflow. This implementation has no remote and has not been pushed.

## Publish workflow

`run.bat deploy` contains the copied maintainer menu: publish, copy local startup settings, combined publish/copy, previews, permission helper and release. Configure the target through `tools/deploy.local.ini`, using `tools/deploy.local.example.ini` as a template. These publishing actions require separate authorization and were not run here.

## First-time setup

Copy the source project to the deployment machine, excluding local environments, runtime data and private settings. In that folder, create `.env` from `.env.example` locally and set `SERVICE_ADMIN_PASSWORD`. See [Settings](guide-docker-same-device.md#settings).

## Start

```bash
docker compose up -d --build
```

## Check

```bash
curl http://127.0.0.1:29406/health
```

Open `/admin/`, sign in and create a caller token. Open `/admin/gateways.html`, enter the admin password, save a gateway reachable from this machine and press **Test**. Configure callers with the machine address and their own token.

## Updating

Replace source with an approved version, then rebuild:

```bash
docker compose up -d --build
```

The data volume preserves saved gateways, tokens and settings. No model or weights are stored by DecisionGateway.

## Releasing

The copied maintainer tools support versioned ZIP files and a `live` branch release. Keep `VERSION` and `pyproject.toml` versions equal. Publishing and tagging remain outside the current authorization; no remote has been added.

## Problems

See [Problems](guide-docker-same-device.md#problems). Docker build and remote deployment remain unverified.
