"""The DecisionGateway server: decide, gateways, validate and health, plus the admin routes."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from src import gateways_api
from src.admin_api import Backends, Usage, register
from src.config import PROJECT_DIR, Settings
from src.contract import parse_questions, parse_request
from src.errors import GatewayError
from src.middleware import TokenMiddleware
from src.options import live, make_config
from src.runtime import Config
from src.service import DecisionService
from src.store import GatewayStore
from src.tokens import TokenStore

WEB_DIR = Path(os.environ.get("SERVICE_WEB_DIR") or PROJECT_DIR / "web")
MAX_BODY = 32 * 1024 * 1024
INSTRUCTIONS = "DecisionGateway has no MCP tools. Use POST /api/decide."

CONNECT = {
    "host": "decisiongateway",
    "port": 29406,
    "paths": [
        {"label": "Decide", "method": "POST", "path": "/api/decide"},
        {"label": "Gateways", "method": "GET", "path": "/api/gateways"},
        {"label": "Validate questions", "method": "POST", "path": "/api/validate"},
        {"label": "Gateways admin page", "method": "GET", "path": "/admin/gateways.html"},
        {"label": "Health, no token", "method": "GET", "path": "/health"},
    ],
}


def _error(error: GatewayError) -> JSONResponse:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    return JSONResponse({"error": error.code, "message": error.message}, status_code=error.status, headers=headers)


def build_app(settings: Settings, config: Config | None = None, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    config = config if config is not None else make_config(settings)
    base, settings = settings, live(settings, config)
    store = GatewayStore(base.state_dir / "gateways.json")
    service = DecisionService(store, settings, transport)
    usage = Usage()
    tokens = TokenStore(base.state_dir / "tokens.json", "dg_")
    mcp = FastMCP(name="decisiongateway", instructions=INSTRUCTIONS, host=settings.host, port=settings.port)

    async def body_of(request: Request) -> Any:
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_BODY:
            raise GatewayError(413, "too_large", "The request is larger than 32 MiB.")
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise GatewayError(413, "too_large", "The request is larger than 32 MiB.")
        try:
            return json.loads(raw)
        except ValueError:
            raise GatewayError(422, "invalid_request", "Invalid decision request: the body must be JSON.") from None

    def lines(items: AsyncIterator[dict[str, Any]], first: dict[str, Any]) -> AsyncIterator[bytes]:
        async def generate() -> AsyncIterator[bytes]:
            yield (json.dumps(first) + "\n").encode()
            try:
                async for item in items:
                    yield (json.dumps(item) + "\n").encode()
            except GatewayError as error:
                yield (json.dumps({"type": "error", "status": error.status, "detail": error.message}) + "\n").encode()
        return generate()

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        return JSONResponse({"ok": True, "ready": bool(await asyncio.to_thread(store.all))})

    @mcp.custom_route("/api/decide", methods=["POST"])
    async def decide(request: Request) -> Response:
        owner = request.headers.get("x-requester-username", "").strip() or "unknown"
        try:
            decision = parse_request(await body_of(request), settings.max_chars)
            async with usage.track(owner, "decide"):
                if not decision.stream:
                    return JSONResponse(await service.decide(decision))
                items = service.stream(decision)
                first = await anext(items)  # a pre-flight failure raises here, before the response starts
        except GatewayError as error:
            return _error(error)
        return StreamingResponse(lines(items, first), media_type="application/x-ndjson")

    @mcp.custom_route("/api/gateways", methods=["GET"])
    async def list_gateways(request: Request) -> Response:
        return JSONResponse({"gateways": await service.gateways()})

    @mcp.custom_route("/api/validate", methods=["POST"])
    async def validate(request: Request) -> Response:
        try:
            data = await body_of(request)
            parse_questions(data.get("questions") if isinstance(data, dict) else None)
        except GatewayError as error:
            return _error(error)
        return JSONResponse({"ok": True})

    async def status() -> list[dict[str, str]]:
        rows = await asyncio.to_thread(store.public)
        return [{"label": "Gateways", "value": ", ".join(f"{r['id']} ({r['kind']})" for r in rows) or "none saved"}]

    if config is not None:
        register(mcp, connect=CONNECT, service="DecisionGateway", admin_password=base.admin_password, usage=usage,
                 backends=Backends(base.state_dir / "backends.json"), tokens=tokens, status=status, slots=[])
        gateways_api.register(mcp, admin_password=base.admin_password, store=store, service=service)

    app = mcp.streamable_http_app()
    if config is not None and WEB_DIR.is_dir():
        app.router.routes.append(Mount("/admin", StaticFiles(directory=WEB_DIR, html=True)))
    app.add_middleware(TokenMiddleware, tokens=tokens if base.admin_password else None)
    return app
