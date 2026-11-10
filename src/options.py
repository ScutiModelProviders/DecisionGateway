"""The options the admin page can change. A saved value wins over the environment value shown as default."""
from __future__ import annotations

from src.config import Settings
from src.runtime import Config, LiveSettings, Setting

FIELDS = {  # Settings attribute -> (setting key, conversion)
    "max_chars": ("max_chars", int),
    "max_inflight": ("max_inflight", int),
    "cache_enabled": ("cache", bool),
    "cache_seconds": ("cache_seconds", int),
    "cache_entries": ("cache_entries", int),
}


def schema(base: Settings) -> list[Setting]:
    return [
        Setting("max_chars", "Longest text per request (characters)", "int", base.max_chars, minimum=1, maximum=100000),
        Setting("max_inflight", "Decisions at once", "int", base.max_inflight, minimum=1, maximum=256,
                help="More than this many at once get 429 with Retry-After."),
        Setting("cache", "Keep answers (cache)", "bool", base.cache_enabled),
        Setting("cache_seconds", "Keep cached answers for (seconds)", "int", base.cache_seconds, minimum=1, maximum=86400),
        Setting("cache_entries", "Cached answers kept", "int", base.cache_entries, minimum=1, maximum=100000),
        Setting("data_path", "Data folder", "text", "", restart=True,
                help=f"Where stored data goes. Empty = {base.state_dir}. Applies after a restart; files already stored are not moved."),
    ]


def make_config(base: Settings) -> Config | None:
    """None, so nothing is changeable at run time, unless SERVICE_ADMIN_PASSWORD is set."""
    return Config(base.state_dir / "settings.json", schema(base)) if base.admin_password else None


def live(base: Settings, config: Config | None):
    return LiveSettings(base, config, FIELDS) if config else base
