# Deploying DecisionGateway

DecisionGateway is one HTTP service on port 29406, with no local model: callers reach it directly or at `http://decisiongateway:29406` on `citadel_core`.

## Ways to run it

| Path | Guide |
|---|---|
| Docker Desktop on this PC | [Docker on this PC](docs/guide-docker-same-device.md) |
| Docker on another machine | [Deployment machine](docs/guide-docker-deployment-device.md) |
| Directly on Windows | [Without Docker](docs/guide-no-docker-same-device.md) |

Once it runs, follow [the admin web UI guide](docs/guide-web-ui.md).
