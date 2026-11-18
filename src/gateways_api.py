"""Admin routes for the gateway list. Guarded by X-Admin-Password like the shared admin routes; secrets are write-only."""
from __future__ import annotations

import asyncio
import hmac
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.errors import GatewayError
from src.presets import MODEL_LISTS, PRESETS
from src.service import DecisionService
from src.store import GatewayStore, KINDS

FORM = {  # what the page shows per kind: (field, label, secret, required)
    "typesafe": [("url", "Address", False, False), ("model", "Model", False, True), ("api_key", "API key", True, True)],
    "ollama": [("url", "Ollama address", False, True), ("model", "Model", False, True)],
    "scuti": [("url", "Model service address", False, True), ("token", "Token", True, False),
              ("strategy", "Strategy", False, False), ("window", "Window (tokens)", False, False)],
}


def register(mcp: FastMCP, *, admin_password: str, store: GatewayStore, service: DecisionService) -> None:
    def denied(request: Request) -> Response | None:
        given = request.headers.get("x-admin-password", "").encode("utf-8")
        if not hmac.compare_digest(given, admin_password.encode("utf-8")):
            return JSONResponse({"detail": "Wrong admin password."}, status_code=401)
        return None

    @mcp.custom_route("/admin/gateways", methods=["GET"])
    async def gateways(request: Request) -> Response:
        if (refused := denied(request)) is not None:
            return refused
        return JSONResponse({"gateways": await service.gateways(), "kinds": {k: FORM[k] for k in KINDS},
                             "presets": PRESETS, "model_lists": MODEL_LISTS})

    @mcp.custom_route("/admin/gateways/{gateway_id}", methods=["PUT", "DELETE"])
    async def gateway(request: Request) -> Response:
        if (refused := denied(request)) is not None:
            return refused
        gid = request.path_params["gateway_id"]
        if request.method == "DELETE":
            ok = await asyncio.to_thread(store.delete, gid)
            return JSONResponse({"ok": True} if ok else {"detail": "No such gateway."}, status_code=200 if ok else 404)
        try:
            data: Any = await request.json()
        except ValueError:
            data = None
        try:
            return JSONResponse(await asyncio.to_thread(store.put, gid, data))
        except ValueError as error:
            return JSONResponse({"detail": str(error)}, status_code=422)

    @mcp.custom_route("/admin/gateways/{gateway_id}/test", methods=["POST"])
    async def test(request: Request) -> Response:
        if (refused := denied(request)) is not None:
            return refused
        try:
            return JSONResponse({"ok": True, "message": await service.test(request.path_params["gateway_id"])})
        except GatewayError as error:
            return JSONResponse({"ok": False, "detail": error.message}, status_code=error.status if error.status == 404 else 200)
