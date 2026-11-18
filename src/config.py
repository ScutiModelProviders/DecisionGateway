"""DecisionGateway settings, read from the environment (and a local .env, never committed)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 29406
    data_dir: Path = PROJECT_DIR / ".data"
    config_dir: Path | None = None  # set when the data folder was moved: the folder that keeps settings.json
    max_chars: int = 16000
    max_inflight: int = 8
    cache_enabled: bool = True
    cache_seconds: int = 300
    cache_entries: int = 500
    admin_password: str = ""

    @property
    def state_dir(self) -> Path:
        """Where settings.json, tokens.json and gateways.json live: the first data folder."""
        return self.config_dir or self.data_dir

    @property
    def exposed_without_auth(self) -> bool:
        return not self.admin_password.strip() and self.host not in LOOPBACK_HOSTS


def _from_environment() -> Settings:
    env = os.environ.get
    return Settings(
        host=env("SERVICE_HOST", "127.0.0.1"),
        port=int(env("SERVICE_PORT", "29406")),
        data_dir=Path(env("SERVICE_DATA_DIR") or PROJECT_DIR / ".data"),
        max_chars=int(env("SERVICE_MAX_CHARS", "16000")),
        max_inflight=int(env("SERVICE_MAX_INFLIGHT", "8")),
        cache_enabled=env("SERVICE_CACHE", "on").strip().lower() in ("1", "true", "yes", "on"),
        cache_seconds=int(env("SERVICE_CACHE_SECONDS", "300")),
        cache_entries=int(env("SERVICE_CACHE_ENTRIES", "500")),
        admin_password=env("SERVICE_ADMIN_PASSWORD", ""),
    )


def with_saved_data_path(settings: Settings) -> Settings:
    """The admin setting "Data folder" moves stored data to another folder (read once, at start). Settings, tokens
    and gateways stay in the first folder. A folder that cannot be written is ignored."""
    try:
        saved = json.loads((settings.data_dir / "settings.json").read_text("utf-8")).get("data_path")
    except (OSError, ValueError, AttributeError):
        return settings
    if not isinstance(saved, str) or not saved.strip():
        return settings
    target = Path(saved.strip()).expanduser()
    if not target.is_absolute():
        target = PROJECT_DIR / target
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-test"
        probe.write_text("x")
        probe.unlink()
    except OSError:
        logging.getLogger(__name__).warning("Data folder %s cannot be written; using %s", target, settings.data_dir)
        return settings
    return replace(settings, data_dir=target, config_dir=settings.data_dir)


def load_settings() -> Settings:
    return with_saved_data_path(_from_environment())
