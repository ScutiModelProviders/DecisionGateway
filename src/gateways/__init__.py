"""Gateway kinds. A new kind is one adapter file plus one line in KINDS."""
from __future__ import annotations

from typing import Any

import httpx

from src.gateways.base import BaseGateway
from src.gateways.typesafe import TypeSafeGateway

KINDS: dict[str, type[BaseGateway]] = {"typesafe": TypeSafeGateway}


def build_gateway(gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> BaseGateway:
    return KINDS[entry["kind"]](gateway_id, entry, transport)
