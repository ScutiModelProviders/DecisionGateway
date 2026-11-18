"""Gateways, saved in gateways.json in the state folder. Secrets are write-only: they are read for calls and never
returned. shortcut: secrets are stored in clear text because they must be sent as they are; the file is private to
the data folder. Upgrade to a secret store if the host is shared."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from src import runtime
from src.admin_api import MAX_TOKEN, _valid_url

KINDS = ("typesafe", "ollama", "scuti", "freellmapi")
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_TIMEOUT = 60
_SECRETS = {"api_key": "has_api_key", "token": "has_token"}
_FIELDS = {
    "typesafe": ("url", "api_key", "model"),
    "ollama": ("url", "model"),
    "scuti": ("url", "token", "strategy", "window"),
    "freellmapi": ("url", "api_key", "model"),
}


class GatewayStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return self._read()

    def _read(self) -> dict[str, dict[str, Any]]:
        try:
            data = runtime.load(self._path).get("gateways", {})
        except (OSError, ValueError, AttributeError):
            return {}
        return data if isinstance(data, dict) else {}

    def public(self) -> list[dict[str, Any]]:
        return [self._public(gid, entry) for gid, entry in sorted(self.all().items())]

    @staticmethod
    def _public(gid: str, entry: dict[str, Any]) -> dict[str, Any]:
        out = {"id": gid, **{k: v for k, v in entry.items() if k not in _SECRETS}}
        for secret, flag in _SECRETS.items():
            if secret in _FIELDS.get(entry.get("kind", ""), ()):
                out[flag] = bool(entry.get(secret))
        return out

    def put(self, gid: Any, data: Any) -> dict[str, Any]:
        """Create or update one gateway. Raises ValueError with a message that is safe to show."""
        if not isinstance(gid, str) or not ID.fullmatch(gid):
            raise ValueError("The id must be 1 to 48 characters: lowercase letters, digits, - and _, starting with a letter or digit.")
        if not isinstance(data, dict):
            raise ValueError("Send an object.")
        kind = data.get("kind")
        if kind not in KINDS:
            raise ValueError("The kind must be typesafe, ollama, scuti or freellmapi.")
        with self._lock:
            gateways = self._read()
            old = gateways.get(gid, {}) if gateways.get(gid, {}).get("kind") == kind else {}
            entry = self._clean(kind, data, old)
            gateways[gid] = entry
            runtime.replace(self._path, {"gateways": gateways})
        return self._public(gid, entry)

    @staticmethod
    def _clean(kind: str, data: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
        def text(key: str, label: str, required: bool, limit: int = 300) -> str | None:
            value = data.get(key, old.get(key))
            if value is None or value == "":
                if required:
                    raise ValueError(f"{label} is required.")
                return None
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f"{label} must be text of at most {limit} characters.")
            return value.strip()

        entry: dict[str, Any] = {"kind": kind}
        url = text("url", "The address", kind != "typesafe")
        url = (url or TYPESAFE_URL) if kind == "typesafe" else url
        url = url.rstrip("/")
        if not _valid_url(url):
            raise ValueError("The address must look like http://host:port, with no user name, query or fragment.")
        entry["url"] = url
        timeout = data.get("timeout_s", old.get("timeout_s", DEFAULT_TIMEOUT))
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 600:
            raise ValueError("The timeout must be a whole number of seconds from 1 to 600.")
        entry["timeout_s"] = timeout
        if kind == "typesafe":
            entry["model"] = text("model", "The model", True, 100)
            entry["api_key"] = text("api_key", "The API key", True, MAX_TOKEN)
        elif kind == "ollama":
            entry["model"] = text("model", "The model", True, 100)
        elif kind == "freellmapi":
            entry["model"] = text("model", "The model", False, 100) or ""  # empty: FreeLLMAPI picks a decision model
            entry["api_key"] = text("api_key", "The API key", True, MAX_TOKEN)
        else:
            if (token := text("token", "The token", False, MAX_TOKEN)) is not None:
                entry["token"] = token
            if (strategy := text("strategy", "The strategy", False, 60)) is not None:
                entry["strategy"] = strategy
            window = data.get("window", old.get("window"))
            if window is not None:
                if isinstance(window, bool) or not isinstance(window, int) or not 16 <= window <= 8192:
                    raise ValueError("The window must be a whole number from 16 to 8192.")
                entry["window"] = window
        return entry

    def delete(self, gid: str) -> bool:
        with self._lock:
            gateways = self._read()
            if gid not in gateways:
                return False
            del gateways[gid]
            runtime.replace(self._path, {"gateways": gateways})
            return True
