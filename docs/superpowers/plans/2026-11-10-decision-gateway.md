# DecisionGateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tool service `AI/ToolServices/DecisionGateway` (port 29406): one HTTP contract for decision-type models, with config-driven gateways of kind `typesafe`, `ollama` and `scuti`.

**Architecture:** A Starlette app built on `FastMCP` (no tools) like Bard, so the shared admin files work unchanged. `DecisionService` validates a request, picks the named gateway from `GatewayStore`, checks its capabilities, asks it through async httpx and returns one answer shape (or NDJSON lines). Each gateway kind is one adapter file. Gateways are edited on an own page, `web/gateways.html`.

**Tech Stack:** Python 3.11+, FastMCP/Starlette (`mcp==1.28.0`), httpx, pydantic, uvicorn, python-dotenv, pytest + pytest-asyncio, uv.

**Spec:** `AI/ToolServices/DecisionGateway/docs/superpowers/specs/2026-11-10-decision-gateway-design.md`

## Global Constraints

- Project folder: `D:\User\Documents\Programming\AI\ToolServices\DecisionGateway`. All commands run from it. Use absolute paths in tools.
- Port **29406**, env prefix `SERVICE_`, token prefix `dg_`, own git repo, branch `main`.
- Commit author: name from `git -C ../Bard config user.name`, email `214214011+scutiii2@users.noreply.github.com`. Every commit message ends with the line `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Windows: run uv as `UV_CACHE_DIR=D:/User/.uv-cache UV_LINK_MODE=copy uv run pytest -q` (shorthand below: `uv run pytest -q`; always set those two variables).
- HTTP routes are `/api/decide`, `/api/gateways`, `/api/validate` and `/health`. The shared `src/middleware.py` guards only `/mcp` and `/api/*`.
- Shared files are copied byte-for-byte from Bard and never edited here: `src/admin_api.py`, `src/tokens.py`, `src/middleware.py`, `src/runtime.py`, `web/index.html`, `web/playground.js`, `tests/test_admin_api.py`, `tests/test_tokens.py`, `tests/seed.py`, `tests/test_env_file.py`, `tools/check_sync.py`.
- Limits: text at most 16,000 characters (live setting `max_chars`), 1 to 8 questions, 2 to 10 options or levels per question (the same limits as the DSC services; Legion had none), request body at most 32 MiB, each decoded image at most 16 MiB.
- Question types: `choice`, `score`, `noul`, `box`. `box` takes no `criteria`, needs `assets`, and only `typesafe` answers it.
- Answer shape: `type`, the pick (`choice` / `score` / `noul` / `box`), `answer_confidence` (a number, or `null` for a box with no confidence), `uncertain`, `answered_by`. `noul` confidence is `max(noul, 1 - noul)`.
- Errors never contain paths, URLs, credentials or upstream bodies. Secrets (`api_key`, `token`) are write-only: never returned, logged or put in an error.
- No real network in tests: use `httpx.MockTransport`.
- Out of scope: strategies, escalation, `local_only`, MCP tools, multipart or URL images, text generation.

## File Structure

```
src/__init__.py            empty
src/config.py              Settings, load_settings (port 29406)
src/options.py             admin settings schema, live()
src/errors.py              GatewayError(status, code, message, retry_after)
src/contract.py            DecisionRequest, GatewayResult, parse_request, assets_for
src/answers.py             answer_from(spec, raw), mark(...), compact(...)
src/store.py               GatewayStore (gateways.json, write-only secrets)
src/gateways/__init__.py   build_gateway(entry, transport), KINDS
src/gateways/base.py       BaseGateway
src/gateways/typesafe.py   TypeSafeGateway
src/gateways/ollama.py     OllamaGateway
src/gateways/scuti.py      ScutiGateway
src/cache.py               AnswerCache
src/service.py             DecisionService (decide, stream, gateways)
src/gateways_api.py        /admin/gateways routes
src/app.py                 build_app, CONNECT
src/run.py                 python -m src.run
web/gateways.html          gateways admin page
tests/                     one test file per module above, plus the copied shared tests
```

Copied from Bard (shared): see Global Constraints. Project files (Docker, docs, `.env.example`, ...) are Task 10 to 12.

---

### Task 1: Scaffold the repo, copy the shared files, settings

**Files:**
- Create: `pyproject.toml`, `VERSION`, `src/__init__.py`, `src/config.py`, `src/options.py`, `src/errors.py`, `tests/__init__.py`, `tests/test_config.py`
- Copy from `../Bard`: the shared files listed in Global Constraints, plus `web/icon.png`, `web/service-icon.png`, `.gitignore` (from `.agents/skills/tool-service-parity/canonical.gitignore` at the workspace root), `.dockerignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (frozen dataclass: `host, port=29406, data_dir, config_dir, admin_password, max_chars=16000, max_inflight=8, cache_enabled=True, cache_seconds=300, cache_entries=500`, properties `state_dir`, `exposed_without_auth`), `load_settings() -> Settings`, `PROJECT_DIR`, `options.make_config(base) -> Config | None`, `options.live(base, config)`, `GatewayError(status:int, code:str, message:str, retry_after:int|None=None)` with `.status/.code/.message/.retry_after`.

- [ ] **Step 1: Init the repo and copy the shared files**

```bash
cd /d/User/Documents/Programming/AI/ToolServices/DecisionGateway
git init -b main
git config user.name "$(git -C ../Bard config user.name)"
git config user.email "214214011+scutiii2@users.noreply.github.com"
mkdir -p src tests tools web docs .github/workflows
touch src/__init__.py tests/__init__.py
for f in src/admin_api.py src/tokens.py src/middleware.py src/runtime.py web/index.html web/playground.js web/icon.png web/service-icon.png \
         tests/test_admin_api.py tests/test_tokens.py tests/seed.py tests/test_env_file.py tools/check_sync.py .dockerignore .github/workflows/test.yml; do
  cp ../Bard/$f $f
done
cp ../../../.agents/skills/tool-service-parity/canonical.gitignore .gitignore
printf '1.0.0\n' > VERSION
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "decisiongateway"
version = "1.0.0"
description = "One HTTP contract for decision-type models (TypeSafe Jev, Ollama, Scuti model services)"
requires-python = ">=3.11"
dependencies = [
    "mcp==1.28.0",
    "pydantic==2.13.4",
    "uvicorn==0.49.0",
    "python-dotenv==1.2.2",
    "httpx>=0.27",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 3: Write the failing test `tests/test_config.py`**

```python
from src.config import Settings, load_settings
from src.options import live, make_config


def test_defaults():
    s = Settings()
    assert s.port == 29406 and s.max_chars == 16000 and s.max_inflight == 8 and s.cache_enabled


def test_exposed_without_auth():
    assert Settings(host="0.0.0.0").exposed_without_auth
    assert not Settings(host="0.0.0.0", admin_password="pw").exposed_without_auth
    assert not Settings().exposed_without_auth


def test_environment_and_saved_data_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVICE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SERVICE_PORT", "29999")
    assert load_settings().port == 29999
    moved = tmp_path / "moved"
    (tmp_path / "settings.json").write_text('{"data_path": "%s"}' % moved.as_posix(), "utf-8")
    s = load_settings()
    assert s.data_dir == moved and s.state_dir == tmp_path


def test_live_settings_follow_saved_values(tmp_path):
    base = Settings(data_dir=tmp_path, admin_password="pw")
    config = make_config(base)
    settings = live(base, config)
    assert settings.max_chars == 16000
    config.set({"max_chars": 500})
    assert settings.max_chars == 500
    assert make_config(Settings(data_dir=tmp_path)) is None
```

- [ ] **Step 4: Run it, expect FAIL** — `uv sync && uv run pytest tests/test_config.py -q` → `ModuleNotFoundError: src.config`.

- [ ] **Step 5: Write `src/errors.py`, `src/config.py`, `src/options.py`**

`src/errors.py`:
```python
"""The one error every layer raises. `message` is safe to show: no paths, URLs, credentials or upstream text."""
from __future__ import annotations


class GatewayError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.retry_after = status, code, message, retry_after
```

`src/config.py` (copy Bard's `src/config.py` structure; the loopback rule and saved data path stay):
```python
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
```

`src/options.py`:
```python
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
```

- [ ] **Step 6: Run the new and copied tests, expect PASS**

Run: `uv run pytest -q`
Expected: all pass (`test_config.py`, `test_admin_api.py`, `test_tokens.py`, `test_env_file.py`). If a copied test fails because it imports a Bard module, it is not a shared file: stop and report.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: scaffold DecisionGateway with the shared admin files and settings

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Request contract and validation

**Files:**
- Create: `src/contract.py`
- Test: `tests/test_contract.py`

**Interfaces:**
- Consumes: `GatewayError` (Task 1).
- Produces:
  - `DecisionRequest` (frozen dataclass): `gateway: str, text: str, questions: dict[str, dict], assets: dict[str, dict], min_confidence: float | None, trace: bool, stream: bool`.
  - `GatewayResult` (frozen dataclass): `answers: dict[str, dict], tokens: int = 0, model: str = ""`.
  - `parse_request(data: Any, max_chars: int, require_gateway: bool = True) -> DecisionRequest` (raises `GatewayError(422, "invalid_request", ...)`).
  - `parse_questions(questions: Any) -> None` (raises the same).
  - `assets_for(request_text: str, spec: dict, assets: dict) -> dict` — the assets whose placeholder appears in `request_text` or in `json.dumps(spec)`.

- [ ] **Step 1: Write the failing tests `tests/test_contract.py`**

```python
import base64

import pytest

from src.contract import assets_for, parse_questions, parse_request
from src.errors import GatewayError

PNG = base64.b64encode(b"\x89PNG fake").decode()
CHOICE = {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "Invoices", "returns": "Refunds"}}


def body(**extra):
    return {"gateway": "jev", "text": "card charged twice", "questions": {"team": CHOICE}, **extra}


def bad(data, message, **kwargs):
    with pytest.raises(GatewayError) as error:
        parse_request(data, 16000, **kwargs)
    assert error.value.status == 422 and message in error.value.message


def test_minimal_request():
    r = parse_request(body(), 16000)
    assert (r.gateway, r.text, r.assets, r.min_confidence, r.trace, r.stream) == ("jev", "card charged twice", {}, None, False, False)


def test_unknown_field_and_missing_parts():
    bad(body(extra=1), "unknown field")
    bad({**body(), "gateway": ""}, "gateway")
    bad({k: v for k, v in body().items() if k != "text"}, "text")
    with pytest.raises(GatewayError, match="at most 16 characters"):
        parse_request({**body(), "text": "x" * 17}, 16)


def test_gateway_not_required_for_validate():
    data = {k: v for k, v in body().items() if k != "gateway"}
    assert parse_request(data, 16000, require_gateway=False).gateway == ""


@pytest.mark.parametrize("questions,message", [
    ({}, "1 to 8"),
    ({"q": {"type": "pick", "instructions": "x"}}, "type"),
    ({"q": {"type": "choice", "instructions": " ", "criteria": {"a": "x", "b": "y"}}}, "instructions"),
    ({"q": {"type": "choice", "instructions": "x", "criteria": {"a": "x"}}}, "2 to 10"),
    ({"q": {"type": "score", "instructions": "x", "criteria": "no"}}, "list"),
    ({"q": {"type": "noul", "instructions": "x", "criteria": {"yes": "a", "no": "b"}}}, "false"),
    ({"q": {"type": "box", "instructions": "x", "criteria": {"a": "b"}}}, "criteria"),
    ({"q": {"type": "choice", "instructions": "x", "criteria": {"a": "x", "b": "y"}, "extra": 1}}, "unknown field"),
])
def test_bad_questions(questions, message):
    with pytest.raises(GatewayError) as error:
        parse_questions(questions)
    assert message in error.value.message


def test_good_questions_of_every_type():
    parse_questions({
        "c": CHOICE,
        "s": {"type": "score", "instructions": "How urgent?", "criteria": ["low", "high"]},
        "n": {"type": "noul", "instructions": "Billing?"},
        "n2": {"type": "noul", "instructions": "Billing?", "criteria": {"true": "yes", "false": "no"}},
    })


def test_min_confidence_trace_stream_types():
    bad(body(min_confidence=0), "min_confidence")
    bad(body(min_confidence=1.5), "min_confidence")
    bad(body(min_confidence=True), "min_confidence")
    bad(body(trace="yes"), "trace")
    bad(body(stream=1), "stream")
    r = parse_request(body(min_confidence=0.8, trace=True, stream=True), 16000)
    assert (r.min_confidence, r.trace, r.stream) == (0.8, True, True)


def test_assets_valid_and_referenced():
    questions = {"where": {"type": "box", "instructions": "Locate the red box in img1"}}
    data = body(questions=questions, assets={"img1": {"type": "image", "format": "png", "data_base64": PNG}})
    assert parse_request(data, 16000).assets["img1"]["format"] == "png"


@pytest.mark.parametrize("assets,message", [
    ({}, "assets"),
    ({"img1": {"type": "image", "format": "gif", "data_base64": PNG}}, "format"),
    ({"img1": {"type": "audio", "format": "png", "data_base64": PNG}}, "type"),
    ({"img1": {"type": "image", "format": "png", "data_base64": "not base64!!"}}, "base64"),
    ({"img1": {"type": "image", "format": "png"}}, "data_base64"),
    ({"img1": {"type": "image", "format": "png", "data_base64": PNG, "part": "x"}}, "unknown field"),
    ({"zzz": {"type": "image", "format": "png", "data_base64": PNG}}, "not used"),
])
def test_bad_assets(assets, message):
    data = body(text="see img1", assets=assets)
    bad(data, message)


def test_box_needs_assets():
    bad(body(questions={"b": {"type": "box", "instructions": "find it"}}), "box")


def test_asset_size_limit(monkeypatch):
    import src.contract as contract
    monkeypatch.setattr(contract, "MAX_IMAGE_BYTES", 4)
    bad(body(text="img1", assets={"img1": {"type": "image", "format": "png", "data_base64": PNG}}), "16 MiB")


def test_assets_for_picks_only_referenced_placeholders():
    assets = {"a": {"x": 1}, "b": {"x": 2}, "c": {"x": 3}}
    spec = {"type": "noul", "instructions": "is it like b?"}
    assert assets_for("photo a", spec, assets) == {"a": {"x": 1}, "b": {"x": 2}}
```

- [ ] **Step 2: Run, expect FAIL** — `uv run pytest tests/test_contract.py -q` → `ModuleNotFoundError: src.contract`.

- [ ] **Step 3: Write `src/contract.py`**

```python
"""One request shape and one answer container for every gateway, and the single definition of a valid request."""
from __future__ import annotations

import base64
import binascii
import json
import math
from dataclasses import dataclass, field
from typing import Any

from src.errors import GatewayError

QUESTION_TYPES = ("choice", "score", "noul", "box")
MAX_QUESTIONS = 8
MIN_OPTIONS, MAX_OPTIONS = 2, 10
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_PLACEHOLDER_BYTES = 1024
IMAGE_FORMATS = ("png", "jpg", "jpeg")
_REQUEST_KEYS = {"gateway", "text", "questions", "assets", "min_confidence", "trace", "stream"}
_NOUL_KEYS = {"false", "true"}


@dataclass(frozen=True)
class DecisionRequest:
    gateway: str
    text: str
    questions: dict[str, dict[str, Any]]
    assets: dict[str, dict[str, Any]] = field(default_factory=dict)
    min_confidence: float | None = None
    trace: bool = False
    stream: bool = False


@dataclass(frozen=True)
class GatewayResult:
    answers: dict[str, dict[str, Any]]
    tokens: int = 0
    model: str = ""


def _fail(message: str) -> GatewayError:
    return GatewayError(422, "invalid_request", f"Invalid decision request: {message}")


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _check_question(qid: Any, spec: Any) -> None:
    where = f"question {qid!r}"
    if not _is_text(qid):
        raise _fail("question ids must be non-empty strings")
    if not isinstance(spec, dict):
        raise _fail(f"{where} must be an object")
    unknown = set(spec) - {"type", "instructions", "criteria"}
    if unknown:
        raise _fail(f"{where} has unknown field(s): {', '.join(sorted(unknown))}")
    kind, criteria = spec.get("type"), spec.get("criteria")
    if kind not in QUESTION_TYPES:
        raise _fail(f"{where} type must be choice, score, noul or box")
    if not _is_text(spec.get("instructions")):
        raise _fail(f"{where} needs non-empty instructions")
    if kind == "choice":
        ok = (isinstance(criteria, dict) and MIN_OPTIONS <= len(criteria) <= MAX_OPTIONS
              and all(_is_text(k) and _is_text(v) for k, v in criteria.items()))
        rule = f"an object of {MIN_OPTIONS} to {MAX_OPTIONS} option: description strings"
    elif kind == "score":
        ok = (isinstance(criteria, list) and MIN_OPTIONS <= len(criteria) <= MAX_OPTIONS
              and all(_is_text(v) for v in criteria))
        rule = f"a list of {MIN_OPTIONS} to {MAX_OPTIONS} level description strings, lowest first"
    elif kind == "noul":
        ok = criteria is None or (isinstance(criteria, dict) and set(criteria) == _NOUL_KEYS
                                  and all(_is_text(v) for v in criteria.values()))
        rule = 'omitted, or an object with exactly the keys "false" and "true"'
    else:
        ok, rule = criteria is None, "omitted (a box question takes only type and instructions)"
    if not ok:
        raise _fail(f"{where} ({kind}) criteria must be {rule}")


def parse_questions(questions: Any) -> None:
    """Raises GatewayError(422) naming the first thing wrong with the questions."""
    if not isinstance(questions, dict) or not 1 <= len(questions) <= MAX_QUESTIONS:
        raise _fail(f"questions must be an object with 1 to {MAX_QUESTIONS} entries")
    for qid, spec in questions.items():
        _check_question(qid, spec)


def _check_assets(assets: Any, text: str, questions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(assets, dict) or not assets:
        raise _fail("assets must be a non-empty object of placeholder: image")
    haystack = text + json.dumps(questions, ensure_ascii=False)
    for key, asset in assets.items():
        if not _is_text(key) or len(key.encode("utf-8")) > MAX_PLACEHOLDER_BYTES:
            raise _fail("an asset placeholder must be a non-empty string of at most 1024 bytes")
        if not isinstance(asset, dict):
            raise _fail(f"asset {key!r} must be an object")
        unknown = set(asset) - {"type", "format", "data_base64"}
        if unknown:
            raise _fail(f"asset {key!r} has unknown field(s): {', '.join(sorted(unknown))}")
        if asset.get("type") != "image":
            raise _fail(f"asset {key!r} type must be image")
        if asset.get("format") not in IMAGE_FORMATS:
            raise _fail(f"asset {key!r} format must be png, jpg or jpeg")
        data = asset.get("data_base64")
        if not isinstance(data, str) or not data:
            raise _fail(f"asset {key!r} needs data_base64")
        try:
            size = len(base64.b64decode(data, validate=True))
        except (binascii.Error, ValueError):
            raise _fail(f"asset {key!r} data_base64 is not valid base64") from None
        if size > MAX_IMAGE_BYTES:
            raise _fail(f"asset {key!r} is larger than 16 MiB")
        if key not in haystack:
            raise _fail(f"asset {key!r} is not used in the text or any question")
    return assets


def parse_request(data: Any, max_chars: int, require_gateway: bool = True) -> DecisionRequest:
    if not isinstance(data, dict):
        raise _fail("the request must be a JSON object")
    unknown = set(data) - _REQUEST_KEYS
    if unknown:
        raise _fail(f"unknown field(s): {', '.join(sorted(unknown))}")
    gateway = data.get("gateway", "")
    if require_gateway and not _is_text(gateway):
        raise _fail("gateway must be the id of a configured gateway")
    if not isinstance(gateway, str):
        raise _fail("gateway must be text")
    text = data.get("text")
    if not _is_text(text):
        raise _fail("text must be a non-empty string")
    if len(text) > max_chars:
        raise _fail(f"text must be at most {max_chars} characters")
    questions = data.get("questions")
    parse_questions(questions)
    minimum = data.get("min_confidence")
    if minimum is not None and (not _is_number(minimum) or not 0 < minimum <= 1):
        raise _fail("min_confidence must be a number above 0 and at most 1")
    flags = {}
    for name in ("trace", "stream"):
        flags[name] = data.get(name, False)
        if not isinstance(flags[name], bool):
            raise _fail(f"{name} must be true or false")
    assets: dict[str, dict[str, Any]] = {}
    if "assets" in data:
        assets = _check_assets(data["assets"], text, questions)
    if any(spec["type"] == "box" for spec in questions.values()) and not assets:
        raise _fail("a box question needs at least one image in assets")
    return DecisionRequest(gateway.strip(), text, questions, assets, None if minimum is None else float(minimum),
                           flags["trace"], flags["stream"])


def assets_for(text: str, spec: dict[str, Any], assets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The assets one upstream call must carry: those whose placeholder appears in the text or in this question."""
    haystack = text + json.dumps(spec, ensure_ascii=False)
    return {key: asset for key, asset in assets.items() if key in haystack}
```

- [ ] **Step 4: Run, expect PASS** — `uv run pytest tests/test_contract.py -q`. Fix the test file leftover line first if it errors.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: request contract and validation" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`

---

### Task 3: Answer mapping

**Files:**
- Create: `src/answers.py`
- Test: `tests/test_answers.py`

**Interfaces:**
- Consumes: `GatewayError`.
- Produces:
  - `answer_from(spec: dict, raw: dict) -> dict` — validates one native answer (the shape TypeSafe and Ollama return) and returns the shared shape without `uncertain` and `answered_by`. Raises `ValueError` on anything unusable.
  - `mark(answer: dict, spec: dict, minimum: float | None, default: float | None) -> None` — sets `answer["uncertain"]`. `minimum` is the caller's `min_confidence`; `default` is the gateway's own bar.
  - `default_threshold(spec: dict) -> float | None` — Ollama's bars: `choice`/`score` 0.9 with 2 options, else 0.75; `noul` 0.9; `box` `None`.
  - `compact(answer: dict) -> dict` — removes trace keys (`rounds, voters, options, disagreement, resolved_by, eliminated`).

- [ ] **Step 1: Write the failing tests `tests/test_answers.py`**

```python
import pytest

from src.answers import answer_from, compact, default_threshold, mark

CHOICE = {"type": "choice", "instructions": "x", "criteria": {"a": "A", "b": "B", "c": "C"}}
SCORE = {"type": "score", "instructions": "x", "criteria": ["low", "mid", "high"]}
NOUL = {"type": "noul", "instructions": "x"}
BOX = {"type": "box", "instructions": "x"}


def test_choice():
    raw = {"type": "choice", "choice": "a", "confidence": 0.7, "probabilities": {"a": 0.7, "b": 0.2, "c": 0.1}}
    assert answer_from(CHOICE, raw) == {"type": "choice", "choice": "a", "answer_confidence": 0.7,
                                        "probabilities": {"a": 0.7, "b": 0.2, "c": 0.1}}


def test_choice_unknown_option_or_keys_fail():
    with pytest.raises(ValueError):
        answer_from(CHOICE, {"choice": "z", "confidence": 0.7, "probabilities": {"a": 0.7, "b": 0.2, "c": 0.1}})
    with pytest.raises(ValueError):
        answer_from(CHOICE, {"choice": "a", "confidence": 0.7, "probabilities": {"a": 1.0}})


def test_score():
    raw = {"score": 1.5, "confidence": 0.55, "probabilities": {"0": 0.1, "1": 0.5, "2": 0.4}}
    out = answer_from(SCORE, raw)
    assert out["score"] == 1.5 and out["answer_confidence"] == 0.55
    assert out["legend"] == {"0": "low", "1": "mid", "2": "high"}
    with pytest.raises(ValueError):
        answer_from(SCORE, {"score": 3, "confidence": 0.5})


def test_noul_confidence_is_the_stronger_side():
    assert answer_from(NOUL, {"noul": 0.98}) == {"type": "noul", "noul": 0.98, "answer_confidence": 0.98}
    assert answer_from(NOUL, {"noul": 0.1})["answer_confidence"] == 0.9
    with pytest.raises(ValueError):
        answer_from(NOUL, {"noul": 1.4})


def test_box_with_and_without_confidence():
    raw = {"box": {"top": 0.2, "bottom": 0.66, "left": 0.19, "right": 0.68}, "confidence": None}
    out = answer_from(BOX, raw)
    assert out == {"type": "box", "box": raw["box"], "answer_confidence": None}
    assert answer_from(BOX, {**raw, "confidence": 0.8})["answer_confidence"] == 0.8
    with pytest.raises(ValueError):
        answer_from(BOX, {"box": {"top": 0.7, "bottom": 0.2, "left": 0.1, "right": 0.5}})
    with pytest.raises(ValueError):
        answer_from(BOX, {"box": {"top": 0.1, "bottom": 0.2, "left": 0.1}})


def test_mark_uncertain():
    a = {"answer_confidence": 0.8}
    mark(a, CHOICE, None, 0.9)
    assert a["uncertain"] is True
    mark(a, CHOICE, 0.7, 0.9)
    assert a["uncertain"] is False
    mark(a, CHOICE, None, None)
    assert a["uncertain"] is False


def test_mark_box_without_confidence():
    a = {"answer_confidence": None}
    mark(a, BOX, None, None)
    assert a["uncertain"] is False
    mark(a, BOX, 0.5, None)
    assert a["uncertain"] is True


def test_default_threshold():
    assert default_threshold({"type": "choice", "criteria": {"a": "", "b": ""}}) == 0.9
    assert default_threshold(CHOICE) == 0.75
    assert default_threshold(NOUL) == 0.9 and default_threshold(BOX) is None


def test_compact_drops_trace_keys():
    assert compact({"choice": "a", "rounds": 2, "voters": {}, "options": []}) == {"choice": "a"}
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: src.answers`.

- [ ] **Step 3: Write `src/answers.py`**

```python
"""Native answers (TypeSafe's and Ollama's /v1/systemone) in the shared answer shape, and the `uncertain` rule."""
from __future__ import annotations

import math
from typing import Any

TRACE_KEYS = ("rounds", "voters", "options", "disagreement", "resolved_by", "eliminated")
_EPSILON = 1e-9


def _number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _unit(value: Any) -> float:
    if not _number(value) or not 0 <= value <= 1:
        raise ValueError("invalid probability")
    return float(value)


def _confidence(raw: dict[str, Any]) -> float:
    return _unit(raw["confidence"])


def answer_from(spec: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """One native answer, validated against its question. Raises ValueError on anything unusable."""
    kind = spec["type"]
    out: dict[str, Any] = {"type": kind}
    if kind == "choice":
        choice, probabilities = raw["choice"], raw["probabilities"]
        if choice not in spec["criteria"] or set(probabilities) != set(spec["criteria"]):
            raise ValueError("unknown choice")
        out["choice"] = choice
        out["probabilities"] = {key: _unit(value) for key, value in probabilities.items()}
        out["answer_confidence"] = _confidence(raw)
    elif kind == "score":
        score = raw["score"]
        if not _number(score) or not 0 <= score <= len(spec["criteria"]) - 1:
            raise ValueError("invalid score")
        out["score"] = round(float(score), 4)
        out["legend"] = {str(i): level for i, level in enumerate(spec["criteria"])}
        out["answer_confidence"] = _confidence(raw)
    elif kind == "noul":
        noul = _unit(raw["noul"])
        out["noul"] = noul
        out["answer_confidence"] = max(noul, 1 - noul)  # no confidence for yes/no: the stronger side
    else:
        box = raw["box"]
        sides = {name: _unit(box[name]) for name in ("top", "bottom", "left", "right")}
        if sides["top"] >= sides["bottom"] or sides["left"] >= sides["right"]:
            raise ValueError("invalid box")
        out["box"] = sides
        out["answer_confidence"] = None if raw.get("confidence") is None else _confidence(raw)
    return out


def default_threshold(spec: dict[str, Any]) -> float | None:
    """The bars Ollama's d3 uses (Laya English's numbers, not measured for d3): 2 options 0.90, 3 or more 0.75."""
    kind = spec["type"]
    if kind == "box":
        return None
    if kind == "noul":
        return 0.9
    return 0.9 if len(spec["criteria"]) == 2 else 0.75


def mark(answer: dict[str, Any], spec: dict[str, Any], minimum: float | None, default: float | None) -> None:
    """Sets `uncertain`. `minimum` is the caller's min_confidence, `default` the gateway's own bar. A box with no
    confidence is uncertain only when the caller set a minimum, because that bar cannot be checked."""
    confidence = answer["answer_confidence"]
    if confidence is None:
        answer["uncertain"] = minimum is not None
        return
    bar = minimum if minimum is not None else default
    answer["uncertain"] = bar is not None and confidence < bar - _EPSILON


def compact(answer: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in answer.items() if key not in TRACE_KEYS}
```

- [ ] **Step 4: Run, expect PASS** — `uv run pytest tests/test_answers.py -q`.

- [ ] **Step 5: Commit** — message `feat: answer mapping and the uncertain rule`.

---

### Task 4: Gateway store

**Files:**
- Create: `src/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `src.runtime.load(path) -> dict`, `src.runtime.replace(path, data)`, `src.admin_api._valid_url`.
- Produces: `GatewayStore(path)` with `all() -> dict[str, dict]` (full entries, secrets included, for adapters), `public() -> list[dict]` (entries with secrets replaced by `has_api_key` / `has_token` booleans), `put(gateway_id: str, data: dict) -> dict` (returns the public entry; omitted secret keeps the saved one; raises `ValueError` with a safe message), `delete(gateway_id) -> bool`, `KINDS = ("typesafe", "ollama", "scuti")`, `ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")`.

Entry fields per kind: all: `kind`, `timeout_s` (1 to 600, default 60). `typesafe`: `url` (default `https://api.typesafe.ai/v1/systemone`), `api_key` (required on create), `model` (required). `ollama`: `url` (required), `model` (required). `scuti`: `url` (required), `token` (optional), `strategy` (optional), `window` (optional int 16 to 8192).

- [ ] **Step 1: Write the failing tests `tests/test_store.py`**

```python
import json

import pytest

from src.store import GatewayStore


@pytest.fixture
def store(tmp_path):
    return GatewayStore(tmp_path / "gateways.json")


def test_put_returns_public_entry_without_secrets(store, tmp_path):
    entry = store.put("jev", {"kind": "typesafe", "api_key": "sk-secret", "model": "jev-latest"})
    assert entry == {"id": "jev", "kind": "typesafe", "url": "https://api.typesafe.ai/v1/systemone",
                     "model": "jev-latest", "timeout_s": 60, "has_api_key": True}
    assert "sk-secret" not in json.dumps(store.public())
    assert store.all()["jev"]["api_key"] == "sk-secret"
    assert (tmp_path / "gateways.json").exists()


def test_omitted_secret_keeps_the_saved_one(store):
    store.put("jev", {"kind": "typesafe", "api_key": "sk-secret", "model": "jev-latest"})
    store.put("jev", {"kind": "typesafe", "model": "jev-preview"})
    assert store.all()["jev"]["api_key"] == "sk-secret" and store.all()["jev"]["model"] == "jev-preview"


def test_kinds_and_required_fields(store):
    with pytest.raises(ValueError, match="kind"):
        store.put("x", {"kind": "magic"})
    with pytest.raises(ValueError, match="API key"):
        store.put("jev", {"kind": "typesafe", "model": "m"})
    with pytest.raises(ValueError, match="model"):
        store.put("d3", {"kind": "ollama", "url": "http://127.0.0.1:11434"})
    with pytest.raises(ValueError, match="address"):
        store.put("d3", {"kind": "ollama", "model": "d3:2b"})
    store.put("d3", {"kind": "ollama", "url": "http://127.0.0.1:11434/", "model": "d3:2b"})
    assert store.all()["d3"]["url"] == "http://127.0.0.1:11434"
    store.put("laya", {"kind": "scuti", "url": "http://127.0.0.1:29220", "token": "t", "strategy": "auto", "window": 4096})
    assert store.public()[-1]["has_token"] is True


@pytest.mark.parametrize("bad_id", ["", "Jev", "-x", "a b", "x" * 49])
def test_bad_ids(store, bad_id):
    with pytest.raises(ValueError, match="id"):
        store.put(bad_id, {"kind": "scuti", "url": "http://127.0.0.1:1"})


def test_bad_url_timeout_window(store):
    with pytest.raises(ValueError, match="address"):
        store.put("a", {"kind": "scuti", "url": "ftp://x"})
    with pytest.raises(ValueError, match="address"):
        store.put("a", {"kind": "scuti", "url": "http://user:pw@host"})
    with pytest.raises(ValueError, match="timeout"):
        store.put("a", {"kind": "scuti", "url": "http://h:1", "timeout_s": 0})
    with pytest.raises(ValueError, match="window"):
        store.put("a", {"kind": "scuti", "url": "http://h:1", "window": 5})


def test_delete(store):
    store.put("a", {"kind": "scuti", "url": "http://h:1"})
    assert store.delete("a") is True and store.delete("a") is False and store.all() == {}


def test_corrupt_file_reads_as_empty(tmp_path):
    path = tmp_path / "gateways.json"
    path.write_text("{not json", "utf-8")
    assert GatewayStore(path).all() == {}
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: src.store`.

- [ ] **Step 3: Write `src/store.py`**

```python
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

KINDS = ("typesafe", "ollama", "scuti")
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_TIMEOUT = 60
_SECRETS = {"api_key": "has_api_key", "token": "has_token"}
_FIELDS = {
    "typesafe": ("url", "api_key", "model"),
    "ollama": ("url", "model"),
    "scuti": ("url", "token", "strategy", "window"),
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
            raise ValueError("The kind must be typesafe, ollama or scuti.")
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
```

- [ ] **Step 4: Run, expect PASS** — `uv run pytest tests/test_store.py -q`. Adjust only the error-message wording the tests match (`id`, `kind`, `API key`, `model`, `address`, `timeout`, `window`).

- [ ] **Step 5: Commit** — message `feat: gateway store with write-only secrets`.

---

### Task 5: Gateway base, registry and the `typesafe` adapter

**Files:**
- Create: `src/gateways/__init__.py`, `src/gateways/base.py`, `src/gateways/typesafe.py`
- Test: `tests/test_typesafe.py`

**Interfaces:**
- Consumes: `DecisionRequest`, `GatewayResult`, `assets_for` (Task 2); `answer_from`, `mark` (Task 3); `GatewayError`.
- Produces:
  - `BaseGateway`: attributes `id: str`, `kind: str`, `model: str`, `streams: bool`, `images: bool`, `types: frozenset[str]`; methods `async ask(request, timeout=None) -> GatewayResult`, `async probe() -> str` (a short success message or `GatewayError`), `async ask_stream(request, timeout=None)` (async iterator of `("answer", qid, answer)` then `("done", GatewayResult)`; only gateways with `streams=True`).
  - `build_gateway(gateway_id: str, entry: dict, transport: httpx.AsyncBaseTransport | None = None) -> BaseGateway` in `src/gateways/__init__.py`; `KINDS` maps kind to class.
  - `TypeSafeGateway(gateway_id, entry, transport=None)`; `streams=False, images=True`, `types={"choice","score","noul","box"}`.
  - Shared helper in `base.py`: `async def upstream_post(client, url, *, json, headers, timeout, name) -> dict` mapping httpx failures to `GatewayError` (see below).

Error mapping used by all adapters (`upstream_post(..., name)`): timeout or connect error → `GatewayError(502, "gateway_unreachable", f"{name} could not be reached.")`; HTTP 400 → `422, "gateway_refused", f"{name} refused the request. Check the images, the question types and the model."`; 401/403 → `502, "gateway_auth", f"{name} refused the credentials."`; 413 → `413, "too_large", f"{name} says the request is too large."`; 429/529 → `503, "gateway_busy", f"{name} is busy.", retry_after=1`; any other ≥400 → `502, "gateway_error", f"{name} answered an error."`; a body that is not a JSON object → `502, "gateway_bad_reply", f"{name} sent an unusable reply."`. Upstream bodies are never included.

- [ ] **Step 1: Write the failing tests `tests/test_typesafe.py`**

```python
import base64
import json

import httpx
import pytest

from src.contract import DecisionRequest
from src.errors import GatewayError
from src.gateways import build_gateway

PNG = base64.b64encode(b"\x89PNG fake").decode()
ENTRY = {"kind": "typesafe", "url": "https://api.typesafe.ai/v1/systemone", "api_key": "sk-secret", "model": "jev-latest", "timeout_s": 5}
CHOICE = {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "Invoices", "returns": "Refunds"}}


def gateway(handler):
    return build_gateway("jev", ENTRY, httpx.MockTransport(handler))


def reply(answer, tokens=12, model="jev-1.14.0"):
    return httpx.Response(200, json={"model": model, "answers": {"answer": answer}, "usage": {"input_tokens": tokens, "output_tokens": 1}})


def req(questions, **kwargs):
    return DecisionRequest("jev", "card charged twice", questions, **kwargs)


async def test_choice_call_and_mapping():
    seen = {}

    def handler(request):
        seen["auth"], seen["images"] = request.headers["authorization"], request.headers.get("typesafe-danger-zone-images")
        seen["body"] = json.loads(request.content)
        return reply({"type": "choice", "choice": "billing", "confidence": 0.95, "probabilities": {"billing": 0.95, "returns": 0.05}})

    result = await gateway(handler).ask(req({"team": CHOICE}))
    assert seen["auth"] == "Bearer sk-secret" and seen["images"] is None
    assert seen["body"] == {"model": "jev-latest", "state": "card charged twice", "questions": {"answer": CHOICE}}
    answer = result.answers["team"]
    assert answer["choice"] == "billing" and answer["uncertain"] is False
    assert (result.tokens, result.model) == (12, "jev-1.14.0")


async def test_default_bar_is_point_nine_and_caller_minimum_wins():
    low = {"type": "choice", "choice": "billing", "confidence": 0.8, "probabilities": {"billing": 0.8, "returns": 0.2}}
    assert (await gateway(lambda r: reply(low)).ask(req({"team": CHOICE}))).answers["team"]["uncertain"] is True
    assert (await gateway(lambda r: reply(low)).ask(req({"team": CHOICE}, min_confidence=0.7))).answers["team"]["uncertain"] is False


async def test_score_noul_are_sent_natively():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body["questions"]["answer"])
        if body["questions"]["answer"]["type"] == "score":
            return reply({"type": "score", "score": 1.7, "confidence": 0.95, "legend": {"0": "a", "1": "b"}, "probabilities": {"0": 0.1, "1": 0.9}})
        return reply({"type": "noul", "noul": 0.98})

    questions = {"u": {"type": "score", "instructions": "How urgent?", "criteria": ["low", "high"]},
                 "b": {"type": "noul", "instructions": "Billing?"}}
    result = await gateway(handler).ask(req(questions))
    assert {b["type"] for b in bodies} == {"score", "noul"}
    assert result.answers["u"]["score"] == 1.7 and result.answers["b"]["noul"] == 0.98


async def test_images_send_header_and_only_referenced_assets():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append((request.headers.get("typesafe-danger-zone-images"), sorted(body.get("assets", {}))))
        if body["questions"]["answer"]["type"] == "box":
            return reply({"type": "box", "box": {"top": 0.2, "bottom": 0.6, "left": 0.1, "right": 0.5}, "confidence": None})
        return reply({"type": "noul", "noul": 0.9})

    assets = {"imgA": {"type": "image", "format": "png", "data_base64": PNG}, "imgB": {"type": "image", "format": "png", "data_base64": PNG}}
    questions = {"where": {"type": "box", "instructions": "Locate the box in imgA"},
                 "same": {"type": "noul", "instructions": "Is imgB a dog?"}}
    result = await gateway(handler).ask(req(questions, assets=assets, min_confidence=0.5))
    assert sorted(calls) == [("true", ["imgA"]), ("true", ["imgB"])]
    assert result.answers["where"]["box"]["top"] == 0.2 and result.answers["where"]["uncertain"] is True


async def test_no_assets_no_header_when_question_has_none():
    seen = []

    def handler(request):
        seen.append(request.headers.get("typesafe-danger-zone-images"))
        return reply({"type": "noul", "noul": 0.9})

    assets = {"imgA": {"type": "image", "format": "png", "data_base64": PNG}}
    questions = {"a": {"type": "noul", "instructions": "no images here"}}
    await gateway(handler).ask(DecisionRequest("jev", "plain text", questions, assets={}))
    assert seen == [None]


@pytest.mark.parametrize("status,code,http", [(400, "gateway_refused", 422), (401, "gateway_auth", 502), (413, "too_large", 413),
                                               (429, "gateway_busy", 503), (500, "gateway_error", 502)])
async def test_error_mapping_hides_upstream_text(status, code, http):
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: httpx.Response(status, text="secret upstream body sk-secret")).ask(req({"team": CHOICE}))
    assert (error.value.code, error.value.status) == (code, http)
    assert "sk-secret" not in error.value.message and "secret upstream" not in error.value.message


async def test_unreachable_and_bad_reply():
    def boom(request):
        raise httpx.ConnectError("no route to api.typesafe.ai")

    with pytest.raises(GatewayError) as error:
        await gateway(boom).ask(req({"team": CHOICE}))
    assert error.value.code == "gateway_unreachable" and "typesafe.ai" not in error.value.message
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: reply({"type": "choice", "choice": "nope", "confidence": 0.9, "probabilities": {"billing": 0.5, "returns": 0.5}})).ask(req({"team": CHOICE}))
    assert error.value.code == "gateway_bad_reply"


async def test_probe_uses_models_endpoint():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"models": []})

    assert "reachable" in (await gateway(handler).probe()).lower()
    assert seen == ["https://api.typesafe.ai/v1/models"]


def test_capabilities():
    g = gateway(lambda r: reply({}))
    assert (g.streams, g.images, g.kind) == (False, True, "typesafe") and g.types == {"choice", "score", "noul", "box"}
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: src.gateways`.

- [ ] **Step 3: Write `src/gateways/base.py`**

```python
"""What every gateway adapter shares: capabilities, the client, and the safe mapping of upstream failures."""
from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from src.contract import DecisionRequest, GatewayResult
from src.errors import GatewayError


async def upstream_post(client: httpx.AsyncClient, url: str, *, json: dict[str, Any], headers: dict[str, str],
                        timeout: float, name: str, method: str = "POST") -> dict[str, Any]:
    """One upstream call. Every failure becomes a GatewayError whose text holds no URL, key or upstream body."""
    try:
        reply = await client.request(method, url, json=json if method == "POST" else None, headers=headers, timeout=timeout)
    except httpx.HTTPError:
        raise GatewayError(502, "gateway_unreachable", f"{name} could not be reached.") from None
    raise_for_status(reply.status_code, name)
    try:
        body = reply.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise GatewayError(502, "gateway_bad_reply", f"{name} sent an unusable reply.")
    return body


def raise_for_status(status: int, name: str) -> None:
    if status < 400:
        return
    if status == 400:
        raise GatewayError(422, "gateway_refused", f"{name} refused the request. Check the images, the question types and the model.")
    if status in (401, 403):
        raise GatewayError(502, "gateway_auth", f"{name} refused the credentials.")
    if status == 413:
        raise GatewayError(413, "too_large", f"{name} says the request is too large.")
    if status in (429, 529):
        raise GatewayError(503, "gateway_busy", f"{name} is busy.", retry_after=1)
    raise GatewayError(502, "gateway_error", f"{name} answered an error.")


class BaseGateway:
    kind = ""
    streams = False
    images = False
    types: frozenset[str] = frozenset({"choice", "score", "noul"})

    def __init__(self, gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.id, self.entry = gateway_id, entry
        self.model = str(entry.get("model", ""))
        self.timeout = float(entry.get("timeout_s", 60))
        # shortcut: the client lives as long as the process and is not closed on shutdown.
        self._client = httpx.AsyncClient(transport=transport, follow_redirects=False)

    async def ask(self, request: DecisionRequest, timeout: float | None = None) -> GatewayResult:
        raise NotImplementedError

    async def probe(self) -> str:
        raise NotImplementedError

    async def ask_stream(self, request: DecisionRequest, timeout: float | None = None) -> AsyncIterator[tuple]:
        raise NotImplementedError
        yield  # pragma: no cover
```

- [ ] **Step 4: Write `src/gateways/typesafe.py`**

```python
"""Gateway kind `typesafe`: TypeSafe's Jev API (POST /v1/systemone, bearer key). A cloud call, one call per question."""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from src.answers import answer_from, mark
from src.contract import DecisionRequest, GatewayResult, assets_for
from src.errors import GatewayError
from src.gateways.base import BaseGateway, upstream_post

NAME = "TypeSafe"
DEFAULT_BAR = 0.9  # Jev reports one confidence and has no thresholds of its own
_QID = "answer"


class TypeSafeGateway(BaseGateway):
    kind = "typesafe"
    images = True
    types = frozenset({"choice", "score", "noul", "box"})

    def _headers(self, with_images: bool) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.entry['api_key']}", "Content-Type": "application/json"}
        if with_images:
            headers["TypeSafe-Danger-Zone-Images"] = "true"  # the API requires it for any request with an image
        return headers

    async def _one(self, request: DecisionRequest, qid: str, spec: dict[str, Any], timeout: float) -> tuple[str, dict[str, Any], int, str]:
        assets = assets_for(request.text, spec, request.assets)
        payload: dict[str, Any] = {"model": self.model, "state": request.text, "questions": {_QID: spec}}
        if assets:
            payload["assets"] = assets
        body = await upstream_post(self._client, self.entry["url"], json=payload, headers=self._headers(bool(assets)),
                                   timeout=timeout, name=NAME)
        try:
            answer = answer_from(spec, body["answers"][_QID])
            usage = body.get("usage") or {}
            tokens = usage.get("input_tokens", 0)
            tokens = tokens if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0 else 0
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.") from None
        mark(answer, spec, request.min_confidence, DEFAULT_BAR)
        return qid, answer, tokens, str(body.get("model", ""))

    async def ask(self, request: DecisionRequest, timeout: float | None = None) -> GatewayResult:
        limit = self.timeout if timeout is None else min(timeout, self.timeout)
        rows = await asyncio.gather(*(self._one(request, qid, spec, limit) for qid, spec in request.questions.items()))
        model = next((m for *_, m in rows if m), self.model)
        return GatewayResult({qid: answer for qid, answer, _, _ in rows}, sum(t for _, _, t, _ in rows), model)

    async def probe(self) -> str:
        parts = urlsplit(self.entry["url"])
        await upstream_post(self._client, f"{parts.scheme}://{parts.netloc}/v1/models", json={},
                            headers=self._headers(False), timeout=10.0, name=NAME, method="GET")
        return "TypeSafe is reachable and accepts the API key."
```

- [ ] **Step 5: Write `src/gateways/__init__.py`**

```python
"""Gateway kinds. A new kind is one adapter file plus one line in KINDS."""
from __future__ import annotations

from typing import Any

import httpx

from src.gateways.base import BaseGateway
from src.gateways.typesafe import TypeSafeGateway

KINDS: dict[str, type[BaseGateway]] = {"typesafe": TypeSafeGateway}


def build_gateway(gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> BaseGateway:
    return KINDS[entry["kind"]](gateway_id, entry, transport)
```

(Tasks 6 and 7 add `ollama` and `scuti` to `KINDS`.)

- [ ] **Step 6: Run, expect PASS** — `uv run pytest tests/test_typesafe.py -q`.

- [ ] **Step 7: Commit** — message `feat: typesafe gateway (choice, score, noul, box, images)`.

---

### Task 6: The `ollama` adapter

**Files:**
- Create: `src/gateways/ollama.py`
- Modify: `src/gateways/__init__.py` (add `"ollama": OllamaGateway` to `KINDS` and its import)
- Test: `tests/test_ollama.py`

**Interfaces:**
- Consumes: `BaseGateway`, `upstream_post`, `answer_from`, `mark`, `default_threshold`.
- Produces: `OllamaGateway`; `streams=False, images=False`, `types={"choice","score","noul"}`. One call for all questions: `POST {url}/v1/systemone {"model", "state", "questions"}`. A `noul` question with no `criteria` is sent with `{"true": "Yes", "false": "No"}` (d3 needs them). Unavailable Ollama or model → `GatewayError(503, "gateway_not_ready", "The model is unavailable: start Ollama and pull the model.")` for connect errors and HTTP 404/5xx; other mapping from `upstream_post`. `probe` = `POST {url}/api/show {"model"}`.

- [ ] **Step 1: Write the failing tests `tests/test_ollama.py`**

```python
import json

import httpx
import pytest

from src.contract import DecisionRequest
from src.errors import GatewayError
from src.gateways import build_gateway

ENTRY = {"kind": "ollama", "url": "http://127.0.0.1:11434", "model": "d3:2b", "timeout_s": 5}
CHOICE = {"type": "choice", "instructions": "Team?", "criteria": {"a": "A", "b": "B", "c": "C"}}


def gateway(handler):
    return build_gateway("d3", ENTRY, httpx.MockTransport(handler))


async def test_one_call_for_all_questions_and_default_noul_criteria():
    seen = {}

    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.content)
        return httpx.Response(200, json={"answers": {
            "t": {"type": "choice", "choice": "a", "confidence": 0.8, "probabilities": {"a": 0.8, "b": 0.1, "c": 0.1}},
            "n": {"type": "noul", "noul": 0.97}}, "usage": {"input_tokens": 40}})

    questions = {"t": CHOICE, "n": {"type": "noul", "instructions": "Billing?"}}
    result = await gateway(handler).ask(DecisionRequest("d3", "state text", questions))
    assert seen["url"] == "http://127.0.0.1:11434/v1/systemone"
    assert seen["body"]["questions"]["n"]["criteria"] == {"true": "Yes", "false": "No"}
    assert seen["body"]["model"] == "d3:2b" and seen["body"]["state"] == "state text"
    assert result.tokens == 40 and result.model == "d3:2b"
    assert result.answers["t"]["uncertain"] is False   # 0.8 >= 0.75 (three options)
    assert result.answers["n"]["answer_confidence"] == 0.97


async def test_two_option_bar_and_caller_minimum():
    answer = {"type": "choice", "choice": "a", "confidence": 0.8, "probabilities": {"a": 0.8, "b": 0.2}}
    two = {"type": "choice", "instructions": "x", "criteria": {"a": "A", "b": "B"}}
    handler = lambda r: httpx.Response(200, json={"answers": {"q": answer}, "usage": {}})
    assert (await gateway(handler).ask(DecisionRequest("d3", "t", {"q": two}))).answers["q"]["uncertain"] is True
    assert (await gateway(handler).ask(DecisionRequest("d3", "t", {"q": two}, min_confidence=0.5))).answers["q"]["uncertain"] is False


@pytest.mark.parametrize("response", [httpx.ConnectError("down"), httpx.Response(404, text="model not found"),
                                      httpx.Response(500, text="llama crashed at /home/x")])
async def test_unavailable_model_is_503_without_details(response):
    def handler(request):
        if isinstance(response, Exception):
            raise response
        return response

    with pytest.raises(GatewayError) as error:
        await gateway(handler).ask(DecisionRequest("d3", "t", {"q": CHOICE}))
    assert error.value.status == 503 and error.value.code == "gateway_not_ready"
    assert "llama" not in error.value.message and "127.0.0.1" not in error.value.message


async def test_bad_answers_are_a_bad_reply():
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: httpx.Response(200, json={"answers": {"q": {"choice": "zzz"}}})).ask(DecisionRequest("d3", "t", {"q": CHOICE}))
    assert error.value.code == "gateway_bad_reply"


async def test_probe_checks_the_model_is_installed():
    seen = {}

    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.content)
        return httpx.Response(200, json={"details": {}})

    assert "installed" in await gateway(handler).probe()
    assert seen == {"url": "http://127.0.0.1:11434/api/show", "body": {"model": "d3:2b"}}


def test_capabilities():
    g = gateway(lambda r: httpx.Response(200, json={}))
    assert (g.streams, g.images) == (False, False) and "box" not in g.types
```

- [ ] **Step 2: Run, expect FAIL** — `KeyError: 'ollama'` / import error.

- [ ] **Step 3: Write `src/gateways/ollama.py`**

```python
"""Gateway kind `ollama`: a decision model (d3) served by Ollama through /v1/systemone. d3 refuses /api/generate; it
needs criteria on every noul question; Ollama loads the model on the first call."""
from __future__ import annotations

from typing import Any

from src.answers import answer_from, default_threshold, mark
from src.contract import DecisionRequest, GatewayResult
from src.errors import GatewayError
from src.gateways.base import BaseGateway, upstream_post

NAME = "Ollama"
NOUL_DEFAULT = {"true": "Yes", "false": "No"}


def _not_ready() -> GatewayError:
    return GatewayError(503, "gateway_not_ready", "The model is unavailable: start Ollama and pull the model.")


class OllamaGateway(BaseGateway):
    kind = "ollama"
    types = frozenset({"choice", "score", "noul"})

    async def _call(self, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        try:
            body = await upstream_post(self._client, f"{self.entry['url']}{path}", json=payload,
                                       headers={"Content-Type": "application/json"}, timeout=timeout, name=NAME)
        except GatewayError as error:
            if error.code in ("gateway_unreachable", "gateway_error"):
                raise _not_ready() from None
            raise
        if body.get("error"):
            raise _not_ready()
        return body

    async def ask(self, request: DecisionRequest, timeout: float | None = None) -> GatewayResult:
        limit = self.timeout if timeout is None else min(timeout, self.timeout)
        questions = {qid: ({**spec, "criteria": dict(NOUL_DEFAULT)} if spec["type"] == "noul" and spec.get("criteria") is None else spec)
                     for qid, spec in request.questions.items()}
        body = await self._call("/v1/systemone", {"model": self.model, "state": request.text, "questions": questions}, limit)
        try:
            answers = {}
            for qid, spec in request.questions.items():
                answer = answer_from(spec, body["answers"][qid])
                mark(answer, spec, request.min_confidence, default_threshold(spec))
                answers[qid] = answer
            tokens = (body.get("usage") or {}).get("input_tokens", 0)
            tokens = tokens if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0 else 0
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.") from None
        return GatewayResult(answers, tokens, self.model)

    async def probe(self) -> str:
        await self._call("/api/show", {"model": self.model}, 10.0)
        return "Ollama is reachable and the model is installed."
```

Note `answer_from` for a noul question reads the d3 key `noul`; the shared helper ignores `criteria`, so no change is needed there.

- [ ] **Step 4: Register the kind** — in `src/gateways/__init__.py` add `from src.gateways.ollama import OllamaGateway` and `"ollama": OllamaGateway` in `KINDS`.

- [ ] **Step 5: Run, expect PASS** — `uv run pytest tests/test_ollama.py tests/test_typesafe.py -q`.

- [ ] **Step 6: Commit** — message `feat: ollama gateway for d3`.

---

### Task 7: The `scuti` adapter (with native streaming)

**Files:**
- Create: `src/gateways/scuti.py`
- Modify: `src/gateways/__init__.py` (add `"scuti": ScutiGateway`)
- Test: `tests/test_scuti.py`

**Interfaces:**
- Consumes: `BaseGateway`, `upstream_post`, `raise_for_status`.
- Produces: `ScutiGateway`; `streams=True, images=False`, `types={"choice","score","noul"}`. `ask` posts to `{url}/v1/ask` with `{"text", "questions", "trace": request.trace}` plus `strategy` (if saved), `max_len` (from saved `window`), `min_confidence` (if the request has one). Token goes in `X-Internal-Token`. A 429 is retried twice, waiting the `Retry-After` header (0 to 10 s, default 1). Answers pass through as the service returned them; `tokens` = sum of `input_tokens` over `calls`; `model` = the response `model` or `strategy` or `entry.get("model", "")`. `ask_stream` posts the same body with `"stream": true` and yields `("answer", qid, answer)` for each NDJSON `{"type": "answer", "id", "answer"}` line and finally `("done", GatewayResult)` from the `{"type": "done", ...}` line (its `answers`, `calls`, `model`). An `{"type": "error"}` line raises `GatewayError(502, "gateway_error", ...)`. `probe` = `GET {url}/health`; ready if JSON `ready` is not false.

- [ ] **Step 1: Write the failing tests `tests/test_scuti.py`**

```python
import json

import httpx
import pytest

from src.contract import DecisionRequest
from src.errors import GatewayError
from src.gateways import build_gateway

ENTRY = {"kind": "scuti", "url": "http://127.0.0.1:29220", "token": "laya_tok", "strategy": "auto", "window": 4096, "timeout_s": 5}
CHOICE = {"type": "choice", "instructions": "Team?", "criteria": {"a": "A", "b": "B"}}
ANSWER = {"type": "choice", "choice": "a", "probabilities": {"a": 0.95, "b": 0.05}, "answer_confidence": 0.95, "uncertain": False}
BODY = {"strategy": "auto", "model": "laya", "answers": {"q": ANSWER}, "uncertain": [], "calls": [{"input_tokens": 30}, {"input_tokens": 12}]}


def gateway(handler, entry=ENTRY):
    return build_gateway("laya", entry, httpx.MockTransport(handler))


async def test_ask_body_headers_and_summed_tokens():
    seen = {}

    def handler(request):
        seen["url"], seen["token"], seen["body"] = str(request.url), request.headers["x-internal-token"], json.loads(request.content)
        return httpx.Response(200, json=BODY)

    result = await gateway(handler).ask(DecisionRequest("laya", "hello", {"q": CHOICE}, min_confidence=0.8, trace=True))
    assert seen["url"] == "http://127.0.0.1:29220/v1/ask" and seen["token"] == "laya_tok"
    assert seen["body"] == {"text": "hello", "questions": {"q": CHOICE}, "trace": True, "strategy": "auto", "max_len": 4096, "min_confidence": 0.8}
    assert result.answers["q"]["choice"] == "a" and result.tokens == 42 and result.model == "laya"


async def test_optional_fields_are_left_out():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=BODY)

    entry = {"kind": "scuti", "url": "http://127.0.0.1:29221", "timeout_s": 5}
    await gateway(handler, entry).ask(DecisionRequest("d3", "hello", {"q": CHOICE}))
    assert seen["body"] == {"text": "hello", "questions": {"q": CHOICE}, "trace": False}


async def test_busy_service_is_retried_with_retry_after(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("src.gateways.scuti.asyncio.sleep", fake_sleep)
    replies = iter([httpx.Response(429, headers={"retry-after": "2"}), httpx.Response(429, headers={"retry-after": "99"}), httpx.Response(200, json=BODY)])
    result = await gateway(lambda r: next(replies)).ask(DecisionRequest("laya", "t", {"q": CHOICE}))
    assert waits == [2.0, 10.0] and result.answers["q"]["choice"] == "a"


async def test_still_busy_after_retries_is_503(monkeypatch):
    async def no_sleep(seconds):
        return None

    monkeypatch.setattr("src.gateways.scuti.asyncio.sleep", no_sleep)
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: httpx.Response(429)).ask(DecisionRequest("laya", "t", {"q": CHOICE}))
    assert error.value.status == 503


@pytest.mark.parametrize("response,status", [(httpx.Response(422, json={"detail": "bad"}), 422), (httpx.Response(413), 413), (httpx.Response(502, json={"detail": {"message": "x"}}), 502)])
async def test_errors_are_mapped(response, status):
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: response).ask(DecisionRequest("laya", "t", {"q": CHOICE}))
    assert error.value.status == status and "bad" not in error.value.message


async def test_stream_relays_answers_then_done():
    lines = [{"type": "answer", "id": "q", "answer": ANSWER}, {"type": "done", **BODY}]
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines).encode(), headers={"content-type": "application/x-ndjson"})

    items = [item async for item in gateway(handler).ask_stream(DecisionRequest("laya", "t", {"q": CHOICE}, stream=True))]
    assert seen["body"]["stream"] is True
    assert items[0] == ("answer", "q", ANSWER)
    assert items[1][0] == "done" and items[1][1].tokens == 42 and items[1][1].answers["q"]["choice"] == "a"


async def test_stream_error_line():
    content = json.dumps({"type": "error", "status": 502, "detail": "secret"}).encode()
    with pytest.raises(GatewayError) as error:
        [i async for i in gateway(lambda r: httpx.Response(200, content=content)).ask_stream(DecisionRequest("laya", "t", {"q": CHOICE}, stream=True))]
    assert error.value.status == 502 and "secret" not in error.value.message


async def test_probe_reports_not_ready():
    assert "ready" in (await gateway(lambda r: httpx.Response(200, json={"status": "ok", "ready": True})).probe()).lower()
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: httpx.Response(200, json={"status": "ok", "ready": False})).probe()
    assert error.value.status == 503


def test_capabilities():
    g = gateway(lambda r: httpx.Response(200, json={}))
    assert (g.streams, g.images) == (True, False) and g.types == {"choice", "score", "noul"}
```

- [ ] **Step 2: Run, expect FAIL** — `KeyError: 'scuti'`.

- [ ] **Step 3: Write `src/gateways/scuti.py`**

```python
"""Gateway kind `scuti`: a DSC_* model service (DSC_Laya_Model, DSC_D3_Model). Both answer the Laya-shaped POST /v1/ask."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import httpx

from src.contract import DecisionRequest, GatewayResult
from src.errors import GatewayError
from src.gateways.base import BaseGateway, raise_for_status, upstream_post

NAME = "The model service"
BUSY_RETRIES = 2
MAX_WAIT = 10.0


def _body(entry: dict[str, Any], request: DecisionRequest, stream: bool) -> dict[str, Any]:
    body: dict[str, Any] = {"text": request.text, "questions": request.questions, "trace": request.trace}
    if entry.get("strategy"):
        body["strategy"] = entry["strategy"]
    if entry.get("window"):
        body["max_len"] = entry["window"]
    if request.min_confidence is not None:
        body["min_confidence"] = request.min_confidence
    if stream:
        body["stream"] = True
    return body


def _result(entry: dict[str, Any], body: dict[str, Any]) -> GatewayResult:
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.")
    tokens = sum(c.get("input_tokens") or 0 for c in body.get("calls", []) if isinstance(c, dict))
    return GatewayResult(answers, tokens, str(body.get("model") or body.get("strategy") or entry.get("model", "")))


class ScutiGateway(BaseGateway):
    kind = "scuti"
    streams = True

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self.entry["token"]} if self.entry.get("token") else {}

    @staticmethod
    def _wait(reply_headers: httpx.Headers) -> float:
        try:
            wait = float(reply_headers.get("retry-after", ""))
        except ValueError:
            wait = 1.0
        return min(max(wait, 0.0), MAX_WAIT)

    async def ask(self, request: DecisionRequest, timeout: float | None = None) -> GatewayResult:
        limit = self.timeout if timeout is None else min(timeout, self.timeout)
        url, payload = f"{self.entry['url']}/v1/ask", _body(self.entry, request, False)
        for attempt in range(BUSY_RETRIES + 1):
            try:
                reply = await self._client.post(url, json=payload, headers=self._headers(), timeout=limit)
            except httpx.HTTPError:
                raise GatewayError(502, "gateway_unreachable", f"{NAME} could not be reached.") from None
            if reply.status_code != 429 or attempt == BUSY_RETRIES:
                break
            await asyncio.sleep(self._wait(reply.headers))
        raise_for_status(reply.status_code, NAME)
        try:
            body = reply.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.")
        return _result(self.entry, body)

    async def ask_stream(self, request: DecisionRequest, timeout: float | None = None) -> AsyncIterator[tuple]:
        limit = self.timeout if timeout is None else min(timeout, self.timeout)
        try:
            async with self._client.stream("POST", f"{self.entry['url']}/v1/ask", json=_body(self.entry, request, True),
                                           headers=self._headers(), timeout=limit) as reply:
                if reply.status_code >= 400:
                    await reply.aread()
                    raise_for_status(reply.status_code, NAME)
                async for line in reply.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except ValueError:
                        raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.") from None
                    kind = item.get("type") if isinstance(item, dict) else None
                    if kind == "answer" and isinstance(item.get("answer"), dict):
                        yield "answer", str(item.get("id")), item["answer"]
                    elif kind == "done":
                        yield "done", _result(self.entry, item)
                        return
                    elif kind == "error":
                        raise GatewayError(502, "gateway_error", f"{NAME} stopped answering.")
        except httpx.HTTPError:
            raise GatewayError(502, "gateway_unreachable", f"{NAME} could not be reached.") from None

    async def probe(self) -> str:
        body = await upstream_post(self._client, f"{self.entry['url']}/health", json={}, headers={}, timeout=10.0, name=NAME, method="GET")
        if body.get("ready") is False:
            raise GatewayError(503, "gateway_not_ready", f"{NAME} is running but not ready (its model is not loaded).")
        return "The model service is reachable and ready."
```

- [ ] **Step 4: Register the kind** — add `from src.gateways.scuti import ScutiGateway` and `"scuti": ScutiGateway` to `KINDS`.

- [ ] **Step 5: Run, expect PASS** — `uv run pytest tests/test_scuti.py -q`.
- [ ] **Step 6: Commit** — message `feat: scuti gateway with native streaming`.

---

### Task 8: Decision service (cache, limits, capabilities, streaming)

**Files:**
- Create: `src/cache.py`, `src/service.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Consumes: `GatewayStore`, `build_gateway`, `DecisionRequest`, `GatewayResult`, `compact`, `GatewayError`, live `Settings` (`max_inflight`, `cache_enabled`, `cache_seconds`, `cache_entries`).
- Produces:
  - `AnswerCache(get_enabled, get_seconds, get_entries)` with `get(key) -> dict | None`, `put(key, value)`, `static key(request) -> str`.
  - `DecisionService(store, settings, transport=None)`:
    - `async decide(request) -> dict` → `{"gateway", "model", "answers", "tokens", "streamed": False}`.
    - `async stream(request) -> AsyncIterator[dict]` → NDJSON items: `{"type":"answer","id","answer"}` per question then `{"type":"done", **body}`. Raises `GatewayError` before the first item for any pre-flight failure.
    - `async gateways() -> list[dict]` → public entry + `streams, images, types (sorted list), reachable (bool)`. Reachability probes run concurrently with a 3 s limit and are kept 15 s.
    - `async test(gateway_id) -> str` → `gateway.probe()` message; raises `GatewayError(404, "unknown_gateway", ...)`.
  - Capability checks (all before any upstream call, all `GatewayError(422, ...)`): unknown gateway; `assets` sent to a gateway with `images=False` ("The gateway 'X' cannot read images."); a question type not in `gateway.types` ("The gateway 'X' does not answer box questions.").
  - In-flight cap: more than `max_inflight` running decisions → `GatewayError(429, "busy", "Too many decisions at once.", retry_after=1)`.
  - Every answer gets `answered_by = gateway id`; without `request.trace` the trace keys are removed.

- [ ] **Step 1: Write the failing tests `tests/test_service.py`**

```python
import asyncio
import base64
import json

import httpx
import pytest

from src.config import Settings
from src.contract import parse_request
from src.errors import GatewayError
from src.service import DecisionService
from src.store import GatewayStore

PNG = base64.b64encode(b"\x89PNG fake").decode()
CHOICE = {"type": "choice", "instructions": "Team?", "criteria": {"a": "A", "b": "B"}}
LAYA_ANSWER = {"type": "choice", "choice": "a", "probabilities": {"a": 0.95, "b": 0.05}, "answer_confidence": 0.95,
               "uncertain": False, "rounds": 2, "voters": {"x": 1}}


def make(tmp_path, handler, **settings):
    store = GatewayStore(tmp_path / "gateways.json")
    store.put("laya", {"kind": "scuti", "url": "http://127.0.0.1:29220"})
    store.put("jev", {"kind": "typesafe", "api_key": "sk-secret", "model": "jev-latest"})
    store.put("d3", {"kind": "ollama", "url": "http://127.0.0.1:11434", "model": "d3:2b"})
    calls = []

    def counting(request):
        calls.append(str(request.url))
        return handler(request)

    return DecisionService(store, Settings(**settings), httpx.MockTransport(counting)), calls


def laya_handler(request):
    body = json.loads(request.content)
    if body.get("stream"):
        lines = [{"type": "answer", "id": "q", "answer": LAYA_ANSWER},
                 {"type": "done", "model": "laya", "answers": {"q": LAYA_ANSWER}, "calls": [{"input_tokens": 5}]}]
        return httpx.Response(200, content="\n".join(map(json.dumps, lines)).encode())
    return httpx.Response(200, json={"model": "laya", "answers": {"q": LAYA_ANSWER}, "calls": [{"input_tokens": 5}]})


def req(**extra):
    return parse_request({"gateway": "laya", "text": "hello", "questions": {"q": CHOICE}, **extra}, 16000)


async def test_decide_sets_answered_by_and_drops_trace_keys(tmp_path):
    service, _ = make(tmp_path, laya_handler)
    body = await service.decide(req())
    assert body["gateway"] == "laya" and body["streamed"] is False and body["tokens"] == 5
    answer = body["answers"]["q"]
    assert answer["answered_by"] == "laya" and "rounds" not in answer and "voters" not in answer
    assert "rounds" in (await service.decide(req(trace=True)))["answers"]["q"]


async def test_unknown_gateway_and_capability_checks_make_no_upstream_call(tmp_path):
    service, calls = make(tmp_path, laya_handler)
    with pytest.raises(GatewayError, match="unknown|Unknown|no gateway"):
        await service.decide(parse_request({"gateway": "nope", "text": "t", "questions": {"q": CHOICE}}, 16000))
    box = {"gateway": "laya", "text": "see img1", "questions": {"b": {"type": "box", "instructions": "find it in img1"}},
           "assets": {"img1": {"type": "image", "format": "png", "data_base64": PNG}}}
    with pytest.raises(GatewayError, match="cannot read images"):
        await service.decide(parse_request(box, 16000))
    with pytest.raises(GatewayError, match="box"):
        await service.decide(parse_request({**box, "gateway": "d3"}, 16000))
    assert calls == []


async def test_cache_hit_skips_the_gateway_and_stream_is_not_in_the_key(tmp_path):
    service, calls = make(tmp_path, laya_handler)
    await service.decide(req())
    await service.decide(req())
    await service.decide(req(stream=True))
    assert len(calls) == 1
    await service.decide(req(min_confidence=0.5))
    assert len(calls) == 2


async def test_cache_can_be_switched_off(tmp_path):
    service, calls = make(tmp_path, laya_handler, cache_enabled=False)
    await service.decide(req())
    await service.decide(req())
    assert len(calls) == 2


async def test_native_stream_and_emulated_stream(tmp_path):
    service, _ = make(tmp_path, laya_handler)
    items = [i async for i in service.stream(req(stream=True))]
    assert [i["type"] for i in items] == ["answer", "done"]
    assert items[0]["answer"]["answered_by"] == "laya" and items[1]["streamed"] is True and items[1]["tokens"] == 5

    ollama = lambda r: httpx.Response(200, json={"answers": {"q": {"choice": "a", "confidence": 0.9, "probabilities": {"a": 0.9, "b": 0.1}}}, "usage": {"input_tokens": 3}})
    other = tmp_path / "other"
    other.mkdir()
    service, _ = make(other, ollama)
    emulated = [i async for i in service.stream(parse_request({"gateway": "d3", "text": "t", "questions": {"q": CHOICE}, "stream": True}, 16000))]
    assert [i["type"] for i in emulated] == ["answer", "done"] and emulated[1]["streamed"] is False


async def test_stream_preflight_error_is_raised_before_any_item(tmp_path):
    service, _ = make(tmp_path, laya_handler)
    with pytest.raises(GatewayError):
        async for _ in service.stream(parse_request({"gateway": "nope", "text": "t", "questions": {"q": CHOICE}, "stream": True}, 16000)):
            pass


async def test_inflight_cap(tmp_path):
    gate = asyncio.Event()

    async def slow_transport(request):
        await gate.wait()
        return laya_handler(request)

    store = GatewayStore(tmp_path / "gateways.json")
    store.put("laya", {"kind": "scuti", "url": "http://127.0.0.1:29220"})
    service = DecisionService(store, Settings(max_inflight=1, cache_enabled=False), httpx.MockTransport(slow_transport))
    first = asyncio.create_task(service.decide(req()))
    await asyncio.sleep(0.05)
    with pytest.raises(GatewayError) as error:
        await service.decide(req())
    assert error.value.status == 429 and error.value.retry_after == 1
    gate.set()
    await first


async def test_gateways_listing_has_flags_and_no_secrets(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"ready": True, "models": []})

    service, _ = make(tmp_path, handler)
    rows = {row["id"]: row for row in await service.gateways()}
    assert rows["jev"]["images"] is True and rows["jev"]["types"] == ["box", "choice", "noul", "score"]
    assert rows["laya"]["streams"] is True and rows["laya"]["reachable"] is True
    assert "sk-secret" not in json.dumps(rows)


async def test_test_unknown_gateway(tmp_path):
    service, _ = make(tmp_path, laya_handler)
    with pytest.raises(GatewayError) as error:
        await service.test("nope")
    assert error.value.status == 404
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: src.service`.

- [ ] **Step 3: Write `src/cache.py`**

```python
"""A small in-memory answer cache. `stream` is not part of the key, so a streamed answer fills the cache for plain calls."""
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable

from src.contract import DecisionRequest


class AnswerCache:
    def __init__(self, enabled: Callable[[], bool], seconds: Callable[[], int], entries: Callable[[], int]) -> None:
        self._enabled, self._seconds, self._entries = enabled, seconds, entries
        self._rows: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()

    @staticmethod
    def key(request: DecisionRequest) -> str:
        assets = {name: hashlib.sha256(asset["data_base64"].encode()).hexdigest() for name, asset in request.assets.items()}
        raw = json.dumps([request.gateway, request.text, request.questions, assets, request.min_confidence, request.trace],
                         sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self._enabled():
            return None
        row = self._rows.get(key)
        if row is None or time.monotonic() - row[0] > self._seconds():
            self._rows.pop(key, None)
            return None
        self._rows.move_to_end(key)
        return copy.deepcopy(row[1])

    def put(self, key: str, value: dict[str, Any]) -> None:
        if not self._enabled():
            return
        self._rows[key] = (time.monotonic(), copy.deepcopy(value))
        self._rows.move_to_end(key)
        while len(self._rows) > self._entries():
            self._rows.popitem(last=False)
```

- [ ] **Step 4: Write `src/service.py`**

```python
"""Validates which gateway may answer a request, asks it, and shapes the answer. app.py is only transport glue."""
from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

import httpx

from src.answers import compact
from src.cache import AnswerCache
from src.contract import DecisionRequest, GatewayResult
from src.errors import GatewayError
from src.gateways import BaseGateway, build_gateway
from src.store import GatewayStore

REACHABLE_SECONDS = 15.0
PROBE_SECONDS = 3.0


class DecisionService:
    def __init__(self, store: GatewayStore, settings: Any, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._store, self._settings, self._transport = store, settings, transport
        self._gateways: dict[str, tuple[dict[str, Any], BaseGateway]] = {}
        self._cache = AnswerCache(lambda: settings.cache_enabled, lambda: settings.cache_seconds, lambda: settings.cache_entries)
        self._inflight = 0
        self._reachable: dict[str, tuple[float, bool]] = {}

    async def _gateway(self, gateway_id: str) -> BaseGateway:
        entry = (await asyncio.to_thread(self._store.all)).get(gateway_id)
        if entry is None:
            self._gateways.pop(gateway_id, None)
            raise GatewayError(422, "unknown_gateway", f"There is no gateway named '{gateway_id}'.")
        cached = self._gateways.get(gateway_id)
        if cached is None or cached[0] != entry:  # rebuilt when the saved entry changed
            cached = (entry, build_gateway(gateway_id, entry, self._transport))
            self._gateways[gateway_id] = cached
        return cached[1]

    @staticmethod
    def _check(gateway: BaseGateway, request: DecisionRequest) -> None:
        if request.assets and not gateway.images:
            raise GatewayError(422, "images_unsupported", f"The gateway '{gateway.id}' cannot read images.")
        for spec in request.questions.values():
            if spec["type"] not in gateway.types:
                raise GatewayError(422, "type_unsupported", f"The gateway '{gateway.id}' does not answer {spec['type']} questions.")

    def _enter(self) -> None:
        if self._inflight >= self._settings.max_inflight:
            raise GatewayError(429, "busy", "Too many decisions at once.", retry_after=1)
        self._inflight += 1

    def _body(self, gateway: BaseGateway, request: DecisionRequest, result: GatewayResult, streamed: bool) -> dict[str, Any]:
        answers = {}
        for qid, answer in result.answers.items():
            row = {**answer, "answered_by": gateway.id}
            answers[qid] = row if request.trace else compact(row)
        return {"gateway": gateway.id, "model": result.model or gateway.model, "answers": answers,
                "tokens": result.tokens, "streamed": streamed}

    async def decide(self, request: DecisionRequest) -> dict[str, Any]:
        gateway = await self._gateway(request.gateway)
        self._check(gateway, request)
        key = AnswerCache.key(request)
        if (hit := self._cache.get(key)) is not None:
            return hit
        self._enter()
        try:
            result = await gateway.ask(request)
        finally:
            self._inflight -= 1
        body = self._body(gateway, request, result, False)
        self._cache.put(key, body)
        return body

    async def stream(self, request: DecisionRequest) -> AsyncIterator[dict[str, Any]]:
        gateway = await self._gateway(request.gateway)
        self._check(gateway, request)
        key = AnswerCache.key(request)
        hit = self._cache.get(key)
        if hit is None and not gateway.streams:
            hit = await self.decide(request)
        if hit is not None:
            for qid, answer in hit["answers"].items():
                yield {"type": "answer", "id": qid, "answer": answer}
            yield {"type": "done", **hit, "streamed": False}
            return
        self._enter()
        try:
            async for item in gateway.ask_stream(request):
                if item[0] == "answer":
                    _, qid, answer = item
                    row = {**answer, "answered_by": gateway.id}
                    yield {"type": "answer", "id": qid, "answer": row if request.trace else compact(row)}
                else:
                    body = self._body(gateway, request, item[1], True)
                    self._cache.put(key, {**body, "streamed": False})
                    yield {"type": "done", **body}
        finally:
            self._inflight -= 1

    async def _is_reachable(self, gateway: BaseGateway) -> bool:
        seen = self._reachable.get(gateway.id)
        if seen and time.monotonic() - seen[0] < REACHABLE_SECONDS:
            return seen[1]
        try:
            await asyncio.wait_for(gateway.probe(), PROBE_SECONDS)
            ok = True
        except (GatewayError, asyncio.TimeoutError):
            ok = False
        self._reachable[gateway.id] = (time.monotonic(), ok)
        return ok

    async def gateways(self) -> list[dict[str, Any]]:
        rows = await asyncio.to_thread(self._store.public)
        built = [await self._gateway(row["id"]) for row in rows]
        reachable = await asyncio.gather(*(self._is_reachable(g) for g in built))
        return [{**row, "streams": g.streams, "images": g.images, "types": sorted(g.types), "reachable": ok}
                for row, g, ok in zip(rows, built, reachable)]

    async def test(self, gateway_id: str) -> str:
        try:
            gateway = await self._gateway(gateway_id)
        except GatewayError:
            raise GatewayError(404, "unknown_gateway", f"There is no gateway named '{gateway_id}'.") from None
        self._reachable.pop(gateway_id, None)
        return await gateway.probe()
```

Also export `BaseGateway` from `src/gateways/__init__.py` (it already imports it).

- [ ] **Step 5: Run, expect PASS** — `uv run pytest tests/test_service.py -q`.

- [ ] **Step 6: Commit** — message `feat: decision service with cache, in-flight cap, capability checks and streaming`.

---

### Task 9: HTTP app, admin gateway routes and gateways page

**Files:**
- Create: `src/gateways_api.py`, `src/app.py`, `src/run.py`, `web/gateways.html`
- Test: `tests/test_app.py`, `tests/test_gateways_api.py`

**Interfaces:**
- Consumes: `DecisionService`, `GatewayStore`, `parse_request`, `parse_questions`, `GatewayError`, shared `register`, `Usage`, `Backends`, `TokenStore`, `TokenMiddleware`, `make_config`, `live`.
- Produces: `build_app(settings, transport=None) -> Starlette`; `CONNECT` descriptor; admin routes `GET /admin/gateways`, `PUT /admin/gateways/{id}`, `DELETE /admin/gateways/{id}`, `POST /admin/gateways/{id}/test` (header `X-Admin-Password`); API routes `POST /api/decide`, `GET /api/gateways`, `POST /api/validate`, `GET /health`.

Route behavior:
- `POST /api/decide`: body over 32 MiB → 413 `too_large`; invalid JSON → 422; `GatewayError` → `JSONResponse({"error": code, "message": message}, status, headers Retry-After if set)`. `stream: true` → `StreamingResponse(application/x-ndjson)`; the first item is awaited before the response starts so pre-flight errors are normal HTTP errors; a failure later is a final `{"type":"error","status","detail"}` line. Usage is counted with `usage.track(owner, "decide")`, `owner = X-Requester-Username or "unknown"`.
- `GET /api/gateways` → `{"gateways": [...]}`. `POST /api/validate` → `{"ok": true}` or 422 (uses `parse_questions`).
- `GET /health` → `{"ok": true, "ready": <at least one gateway saved>}`.

- [ ] **Step 1: Write the failing tests `tests/test_app.py`**

```python
import base64
import json

import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings
from src.store import GatewayStore
from tests.seed import seed_token

TOKEN = {"X-Internal-Token": "tok"}
CHOICE = {"type": "choice", "instructions": "Team?", "criteria": {"a": "A", "b": "B"}}
ANSWER = {"type": "choice", "choice": "a", "probabilities": {"a": 0.95, "b": 0.05}, "answer_confidence": 0.95, "uncertain": False}
PNG = base64.b64encode(b"\x89PNG fake").decode()


def upstream(request):
    body = json.loads(request.content)
    if str(request.url).endswith("/health"):
        return httpx.Response(200, json={"ready": True})
    if body.get("stream"):
        lines = [{"type": "answer", "id": "q", "answer": ANSWER}, {"type": "done", "model": "laya", "answers": {"q": ANSWER}, "calls": []}]
        return httpx.Response(200, content="\n".join(map(json.dumps, lines)).encode())
    return httpx.Response(200, json={"model": "laya", "answers": {"q": ANSWER}, "calls": [{"input_tokens": 7}]})


@pytest.fixture
def settings(tmp_path):
    GatewayStore(tmp_path / "gateways.json").put("laya", {"kind": "scuti", "url": "http://127.0.0.1:29220", "token": "secret-tok"})
    return seed_token(Settings(data_dir=tmp_path, admin_password="pw"))


@pytest.fixture
def client(settings):
    return TestClient(build_app(settings, transport=httpx.MockTransport(upstream)))


def decide(client, headers=TOKEN, **extra):
    return client.post("/api/decide", headers=headers, json={"gateway": "laya", "text": "hello", "questions": {"q": CHOICE}, **extra})


def test_health_needs_no_token(client):
    assert client.get("/health").json() == {"ok": True, "ready": True}


def test_api_needs_a_token(client):
    assert decide(client, headers={}).status_code == 401
    assert client.get("/api/gateways").status_code == 401


def test_decide(client):
    response = decide(client)
    assert response.status_code == 200
    body = response.json()
    assert body["gateway"] == "laya" and body["tokens"] == 7 and body["answers"]["q"]["answered_by"] == "laya"


@pytest.mark.parametrize("extra,status,code", [
    ({"gateway": "nope"}, 422, "unknown_gateway"),
    ({"questions": {}}, 422, "invalid_request"),
    ({"bogus": 1}, 422, "invalid_request"),
    ({"assets": {"img1": {"type": "image", "format": "png", "data_base64": PNG}}, "text": "see img1"}, 422, "images_unsupported"),
])
def test_decide_errors(client, extra, status, code):
    response = decide(client, **extra)
    assert response.status_code == status and response.json()["error"] == code


def test_invalid_json_and_too_large(client, monkeypatch):
    assert client.post("/api/decide", headers=TOKEN, content=b"{nope").status_code == 422
    monkeypatch.setattr("src.app.MAX_BODY", 10)
    response = client.post("/api/decide", headers=TOKEN, content=b'{"gateway": "laya", "text": "too long"}')
    assert response.status_code == 413 and response.json()["error"] == "too_large"


def test_stream(client):
    with client.stream("POST", "/api/decide", headers=TOKEN, json={"gateway": "laya", "text": "hello", "questions": {"q": CHOICE}, "stream": True}) as response:
        assert response.headers["content-type"].startswith("application/x-ndjson")
        lines = [json.loads(line) for line in response.iter_lines() if line]
    assert [l["type"] for l in lines] == ["answer", "done"] and lines[1]["streamed"] is True


def test_stream_preflight_error_is_a_normal_http_error(client):
    response = decide(client, gateway="nope", stream=True)
    assert response.status_code == 422 and response.json()["error"] == "unknown_gateway"


def test_gateways_and_validate_and_no_secrets(client):
    response = client.get("/api/gateways", headers=TOKEN)
    rows = response.json()["gateways"]
    assert rows[0]["id"] == "laya" and rows[0]["streams"] is True and "secret-tok" not in response.text
    assert client.post("/api/validate", headers=TOKEN, json={"questions": {"q": CHOICE}}).json() == {"ok": True}
    assert client.post("/api/validate", headers=TOKEN, json={"questions": {}}).status_code == 422


def test_busy_maps_to_429_with_retry_after(settings, monkeypatch):
    from src.errors import GatewayError
    from src.service import DecisionService

    async def busy(self, request):
        raise GatewayError(429, "busy", "Too many decisions at once.", retry_after=1)

    monkeypatch.setattr(DecisionService, "decide", busy)
    client = TestClient(build_app(settings, transport=httpx.MockTransport(upstream)))
    response = decide(client)
    assert response.status_code == 429 and response.headers["retry-after"] == "1" and response.json()["error"] == "busy"
```

`tests/test_gateways_api.py`:
```python
import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings

PW = {"X-Admin-Password": "pw"}


@pytest.fixture
def client(tmp_path):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"ready": True, "models": []}))
    return TestClient(build_app(Settings(data_dir=tmp_path, admin_password="pw"), transport=transport))


def test_needs_the_admin_password(client):
    assert client.get("/admin/gateways").status_code == 401
    assert client.put("/admin/gateways/x", json={}).status_code == 401


def test_create_list_test_delete(client):
    created = client.put("/admin/gateways/jev", headers=PW, json={"kind": "typesafe", "api_key": "sk-secret", "model": "jev-latest"})
    assert created.status_code == 200 and created.json()["has_api_key"] is True and "sk-secret" not in created.text
    listing = client.get("/admin/gateways", headers=PW)
    assert [g["id"] for g in listing.json()["gateways"]] == ["jev"] and "sk-secret" not in listing.text
    assert "typesafe" in listing.json()["kinds"]
    assert client.post("/admin/gateways/jev/test", headers=PW).json()["ok"] is True
    assert client.delete("/admin/gateways/jev", headers=PW).status_code == 200
    assert client.delete("/admin/gateways/jev", headers=PW).status_code == 404


def test_bad_input_is_422_with_a_safe_message(client):
    response = client.put("/admin/gateways/jev", headers=PW, json={"kind": "typesafe", "model": "m"})
    assert response.status_code == 422 and "API key" in response.json()["detail"]
    assert client.post("/admin/gateways/missing/test", headers=PW).status_code == 404


def test_page_is_served(client):
    assert "Gateways" in client.get("/admin/gateways.html").text
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: src.app`.

- [ ] **Step 3: Write `src/gateways_api.py`**

```python
"""Admin routes for the gateway list. Guarded by X-Admin-Password like the shared admin routes; secrets are write-only."""
from __future__ import annotations

import asyncio
import hmac
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.errors import GatewayError
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
        return JSONResponse({"gateways": await service.gateways(), "kinds": {k: FORM[k] for k in KINDS}})

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
```

- [ ] **Step 4: Write `src/app.py`**

```python
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
```

`usage.track` wraps the whole decide call including the stream's first item; later stream lines are not counted separately (shortcut: one usage entry per request).

- [ ] **Step 5: Write `src/run.py`** — copy `../Bard/src/run.py` and replace the two `Bard` strings in the refusal message with `DecisionGateway`.

- [ ] **Step 6: Write `web/gateways.html`**

A single static page, no framework, light/dark with `prefers-color-scheme`, labelled form fields, keyboard operable. Behavior:
- An admin password field (kept in memory only). "Load" calls `GET /admin/gateways` with `X-Admin-Password`.
- A table of gateways: id, kind, model/address, `streams`, `images`, `types`, reachable; buttons Test, Edit, Delete.
- A form (id + kind select + the fields from `kinds[kind]`; secret inputs are `type=password`, left empty to keep the saved value, with a "saved" hint when `has_api_key`/`has_token`). Save calls `PUT /admin/gateways/{id}` with only non-empty fields; errors show `detail` in an `aria-live="polite"` region.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gateways · DecisionGateway</title>
<style>
  :root { --bg:#fff; --fg:#1b1f24; --muted:#59636e; --line:#d0d7de; --accent:#0b5fff; --bad:#b42318; --ok:#067647; }
  @media (prefers-color-scheme: dark) { :root { --bg:#14181d; --fg:#e6edf3; --muted:#9aa4af; --line:#30363d; --accent:#6ea0ff; --bad:#ff8b81; --ok:#56d364; } }
  body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; max-width:960px; margin-inline:auto; }
  h1 { font-size:1.3rem; } h2 { font-size:1.05rem; margin-top:1.6rem; }
  label { display:block; margin:.6rem 0 .2rem; font-weight:600; }
  input, select, button { font:inherit; color:inherit; background:var(--bg); border:1px solid var(--line); border-radius:6px; padding:.4rem .6rem; }
  input, select { width:100%; max-width:30rem; box-sizing:border-box; }
  button { cursor:pointer; } button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
  button:focus-visible, input:focus-visible, select:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  table { border-collapse:collapse; width:100%; } th, td { text-align:left; padding:.4rem .5rem; border-bottom:1px solid var(--line); vertical-align:top; }
  .wrap { overflow-x:auto; } .muted { color:var(--muted); } #status { min-height:1.5rem; margin-top:.8rem; } .bad { color:var(--bad); } .ok { color:var(--ok); }
  .row { display:flex; gap:.5rem; flex-wrap:wrap; align-items:end; }
</style>
</head>
<body>
<h1>Gateways</h1>
<p class="muted">Each gateway is one model the service can ask: a TypeSafe Jev model, an Ollama decision model, or a Scuti model service. Callers name a gateway by its id.</p>

<div class="row">
  <div><label for="pw">Admin password</label><input id="pw" type="password" autocomplete="off"></div>
  <button id="load" class="primary" type="button">Load gateways</button>
</div>

<h2>Saved gateways</h2>
<div class="wrap"><table>
  <thead><tr><th>Id</th><th>Kind</th><th>Model or address</th><th>Streams</th><th>Images</th><th>Question types</th><th>Reachable</th><th></th></tr></thead>
  <tbody id="rows"><tr><td colspan="8" class="muted">Enter the admin password and load.</td></tr></tbody>
</table></div>

<h2>Add or change a gateway</h2>
<form id="form">
  <label for="gid">Id</label><input id="gid" required pattern="[a-z0-9][a-z0-9_\-]{0,47}" autocomplete="off">
  <label for="kind">Kind</label><select id="kind"><option>typesafe</option><option>ollama</option><option>scuti</option></select>
  <div id="fields"></div>
  <label for="timeout_s">Timeout (seconds)</label><input id="timeout_s" type="number" min="1" max="600" value="60">
  <p><button class="primary" type="submit">Save gateway</button></p>
</form>
<div id="status" role="status" aria-live="polite"></div>

<script>
let kinds = {};
const $ = (id) => document.getElementById(id);
const say = (text, cls = "") => { $("status").className = cls; $("status").textContent = text; };
const call = async (method, path, body) => {
  const reply = await fetch(path, { method, headers: { "X-Admin-Password": $("pw").value, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const data = await reply.json().catch(() => ({}));
  if (!reply.ok) throw new Error(data.detail || `Request failed (${reply.status})`);
  return data;
};
function drawFields(saved = {}) {
  $("fields").replaceChildren();
  for (const [name, label, secret, required] of kinds[$("kind").value] || []) {
    const l = document.createElement("label"); l.htmlFor = name; l.textContent = label + (required ? " *" : "");
    const i = document.createElement("input"); i.id = name; i.autocomplete = "off"; i.type = secret ? "password" : "text";
    if (secret && saved["has_" + name]) i.placeholder = "saved (leave empty to keep)"; else if (saved[name] != null) i.value = saved[name];
    $("fields").append(l, i);
  }
}
async function load() {
  try {
    const data = await call("GET", "/admin/gateways"); kinds = data.kinds; drawFields();
    const rows = $("rows"); rows.replaceChildren();
    for (const g of data.gateways) {
      const tr = rows.insertRow();
      for (const v of [g.id, g.kind, g.model || g.url, g.streams ? "yes" : "no", g.images ? "yes" : "no", g.types.join(", "), g.reachable ? "yes" : "no"]) tr.insertCell().textContent = v;
      const cell = tr.insertCell();
      for (const [name, fn] of [["Test", () => test(g.id)], ["Edit", () => edit(g)], ["Delete", () => remove(g.id)]]) {
        const b = document.createElement("button"); b.type = "button"; b.textContent = name; b.setAttribute("aria-label", `${name} ${g.id}`); b.onclick = fn; cell.append(b, " ");
      }
    }
    if (!data.gateways.length) rows.insertRow().insertCell().textContent = "No gateways saved yet.";
    say("Loaded.", "ok");
  } catch (e) { say(e.message, "bad"); }
}
function edit(g) { $("gid").value = g.id; $("kind").value = g.kind; drawFields(g); $("timeout_s").value = g.timeout_s; $("gid").focus(); }
async function test(id) { try { const r = await call("POST", `/admin/gateways/${id}/test`); say(r.ok ? `${id}: ${r.message}` : `${id}: ${r.detail}`, r.ok ? "ok" : "bad"); } catch (e) { say(e.message, "bad"); } }
async function remove(id) { if (!confirm(`Delete the gateway "${id}"?`)) return; try { await call("DELETE", `/admin/gateways/${id}`); await load(); } catch (e) { say(e.message, "bad"); } }
$("load").onclick = load;
$("kind").onchange = () => drawFields();
$("form").onsubmit = async (event) => {
  event.preventDefault();
  const body = { kind: $("kind").value, timeout_s: Number($("timeout_s").value) };
  for (const [name] of kinds[body.kind]) { const v = $(name).value.trim(); if (v) body[name] = name === "window" ? Number(v) : v; }
  try { await call("PUT", `/admin/gateways/${$("gid").value}`, body); say("Saved.", "ok"); await load(); } catch (e) { say(e.message, "bad"); }
};
</script>
</body>
</html>
```

- [ ] **Step 7: Run, expect PASS** — `uv run pytest -q`. Everything (copied shared tests included) must pass.

- [ ] **Step 8: Smoke test the real server**

```bash
SERVICE_ADMIN_PASSWORD=pw SERVICE_DATA_DIR=$(mktemp -d) uv run python -m src.run &
curl -s http://127.0.0.1:29406/health
curl -s -X PUT http://127.0.0.1:29406/admin/gateways/laya -H "X-Admin-Password: pw" -H "Content-Type: application/json" -d '{"kind":"scuti","url":"http://127.0.0.1:29220"}'
curl -s http://127.0.0.1:29406/admin/gateways.html | head -5
```
Expected: `{"ok":true,"ready":false}`, then the public entry JSON, then the page's first lines. Stop the server afterwards.

- [ ] **Step 9: Commit** — message `feat: HTTP API, admin gateway routes and gateways page`.

---

### Task 10: Project files (Docker, run scripts, tools, env example)

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.env.example`, `run.bat`, `shell.bat`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, `tools/make_zip.py`, `tools/publish_live.py`, `tools/deploy.local.example.ini`
- Test: `python .agents/skills/tool-service-parity/audit.py tools` (workspace root) and `uv run pytest -q`

- [ ] **Step 1: Copy and rename from Bard**

```bash
for f in run.bat shell.bat tools/make_zip.py tools/publish_live.py tools/deploy.local.example.ini; do cp ../Bard/$f $f; done
sed -i 's/Bard/DecisionGateway/g; s/bard/decisiongateway/g; s/29400/29406/g' run.bat shell.bat tools/make_zip.py tools/publish_live.py tools/deploy.local.example.ini
```
Then edit the `run.bat` header lines by hand: `REM LABEL: DecisionGateway Service` and `REM DESCRIPTION: One HTTP contract for decision-type models (TypeSafe Jev, Ollama, Scuti).` Read each copied file once and fix any leftover Bard-specific text (voices, ffmpeg, Piper).

- [ ] **Step 2: Dockerfile and compose** — from Bard's, without the `apt-get install ffmpeg` block, with `SERVICE_PORT=29406`, `EXPOSE 29406`, the comment `# No model runs here: save gateways on /admin/gateways.html.`; compose `name: decisiongateway`, service `decisiongateway`, volume `decisiongateway_data`, ports `"${SERVICE_BIND:-0.0.0.0}:${SERVICE_PORT:-29406}:29406"`, health check on `http://127.0.0.1:29406/health`, header comments (what it is, `Start:` line, `.env` note, which services to connect), `SERVICE_ADMIN_PASSWORD: ${SERVICE_ADMIN_PASSWORD:?set SERVICE_ADMIN_PASSWORD in .env (it unlocks the token page)}`, and the external `citadel_core` network with its comment.

- [ ] **Step 3: `.env.example`** — only start-up values:

```
# Copy to .env (git-ignored).

SERVICE_HOST=127.0.0.1
SERVICE_PORT=29406

# Docker only: 0.0.0.0 = LAN, 127.0.0.1 = this machine
SERVICE_BIND=0.0.0.0

# Empty = no page and no token checks (loopback only). Required when HOST is not loopback.
SERVICE_ADMIN_PASSWORD=
```

- [ ] **Step 4: `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`** — `CLAUDE.md` is `@AGENTS.md`. `AGENTS.md` follows Bard's structure: one-paragraph description (port 29406, no MCP tools, gateways of kind typesafe/ollama/scuti), Commands (uv sync, `uv run pytest -q`, `run.bat run`), Rules (parity skill, never read `.env`/`gateways.json`/`tokens.json`, logic in `service.py`/`contract.py`/`gateways/`, `app.py` is glue, secrets write-only, no real network in tests, shared files byte-identical and `tools/check_sync.py` must exit 0, the noreply author rule, docs updated in the same commit). `CHANGELOG.md`: `## 1.0.0` with the feature list.

- [ ] **Step 5: Run the audit and tests**

Run (workspace root): `python .agents/skills/tool-service-parity/audit.py tools`
Expected: problems about the missing docs and the `_docs` tables are acceptable now (Tasks 11 and 12 fix them); no problems about layout, `.gitignore`, bat files or compose.
Run: `uv run pytest -q` → PASS.

- [ ] **Step 6: Commit** — message `chore: project files, Docker and run scripts`.

---

### Task 11: Parity in the sibling services and the shared docs (ASK FIRST)

This task edits files outside DecisionGateway (`check_sync.py` in the five existing tool services plus Converse, the shared `_docs`, two skills' audit scripts). The workspace rule says to ask before bulk-editing outside `Brain/`. **Stop and ask the user for a yes before starting this task.**

**Files:**
- Modify: `tools/check_sync.py` in Bard, Scribe, Reader, Lens, Mimic, Converse and DecisionGateway (same content in all seven)
- Modify: `AI/ToolServices/_docs/SHARED-FEATURES.md`, `SERVICE-SPECIFIC.md`, `PURPOSES.md`, `GUIDES.md`, `HARDWARE.md`
- Modify: `.agents/skills/tool-service-parity/audit.py` (`GROUPS["tools"]["names"]`), `.agents/skills/service-docs/docs_audit.py` (`TOOLS`), `.agents/skills/service-groups/purpose_audit.py`, `.agents/skills/tool-service-parity/SKILL.md` (service table)

- [ ] **Step 1: `check_sync.py`** — add `"DecisionGateway"` to `SIBLINGS`. Edit it in DecisionGateway, copy to the six others (`cp`), then run `python tools/check_sync.py` in all seven; each must exit 0. The `SHARED` list stays as it is.

- [ ] **Step 2: `_docs` tables** — add the DecisionGateway row (port 29406, model services it needs: `DSC_Laya_Model`, `DSC_D3_Model`, Ollama, TypeSafe Jev; slot keys: none, gateways instead) to `SHARED-FEATURES.md`'s services table and `PURPOSES.md` (group Decision: "typed questions, optional images → decisions with confidence"), `GUIDES.md`, `HARDWARE.md` (CPU, nothing local). Add to `SERVICE-SPECIFIC.md` a DecisionGateway section listing the differences: no MCP tools (empty `FastMCP` shell), routes `/api/decide`, `/api/gateways`, `/api/validate`, gateways in `gateways.json` edited on `web/gateways.html` (no slots, so the shared Model connections section is empty), tokens prefix `dg_`, answer cache and `max_inflight` settings.

- [ ] **Step 3: Skill scripts** — add `DecisionGateway` to the name lists named above and to the `tool-service-parity` table, port 29406.

- [ ] **Step 4: Verify** — `python .agents/skills/tool-service-parity/audit.py tools`, `python .agents/skills/service-docs/docs_audit.py`, `python .agents/skills/service-groups/purpose_audit.py`; fix what they print for DecisionGateway until each says `0 problem(s)` for it. Do not fix unrelated findings in other services; report them.

- [ ] **Step 5: Commit per repo** — DecisionGateway and each of the six siblings get their own commit (`chore: add DecisionGateway to check_sync`) with the noreply author. Do not push anything.

---

### Task 12: Service documentation and the vault note

**Files:**
- Create: `README.md`, `deployment.md`, `docs/purpose.md`, `docs/guide-web-ui.md`, `docs/guide-docker-same-device.md`, `docs/guide-docker-deployment-device.md`, `docs/guide-no-docker-same-device.md`
- Create: `Brain/Projects/DecisionGateway.md` (via the `project-sync` skill)

Use the `service-docs` and `service-groups` skills; copy the structure of Bard's files and replace the content. Required facts, all taken from the spec and the code:

- [ ] **Step 1: `README.md`** — what it is; the API table (`POST /api/decide` with every request field and the response; `GET /api/gateways`; `POST /api/validate`; `GET /health`); the three gateway kinds with their fields and capability flags (`typesafe`: images yes, box yes, streams no; `ollama`: no images, no box; `scuti`: streams yes, no images, no box); images (`assets` shape, placeholders, 16 MiB, billing note: an image is billed again for every question that uses it); box answers and the `null` confidence rule; streaming and its emulation; errors and statuses; tokens and rate limits; a worked `curl` example for choice, one for an image box question and one with `stream: true`; Connect section (`http://decisiongateway:29406` on `citadel_core`).
- [ ] **Step 2: `deployment.md` and the three `guide-*` setup files** — run steps for Docker same device, Docker on another device, and no Docker; where to save the gateways (`/admin/gateways.html`); the first-run checklist (set `SERVICE_ADMIN_PASSWORD`, make a token, save a gateway, press Test).
- [ ] **Step 3: `docs/guide-web-ui.md`** — the admin pages: Overview, Access tokens, Runtime & settings (including the cache and in-flight settings), Usage, Connect & API, and the Gateways page (fields per kind, write-only secrets, Test).
- [ ] **Step 4: `docs/purpose.md`** — group Decision, input (`text` plus typed questions, optional images), output (answers with confidence and `uncertain`), the models behind it, in the format `service-groups` requires.
- [ ] **Step 5: Vault note** — run the `project-sync` skill for `Brain/Projects/DecisionGateway.md`.
- [ ] **Step 6: Verify** — run the three audits from Task 11 Step 4 again, then `uv run pytest -q` and `python tools/check_sync.py` (exit 0).
- [ ] **Step 7: Commit** — message `docs: README, deployment, guides and purpose`.

---

## Self-review (spec coverage)

- Placement, port 29406, parity, shared files: Tasks 1, 10, 11. `_docs` and audits: Task 11.
- `/api/decide` fields, validation, limits: Task 2. Response, `answered_by`, trace compaction: Task 8. Box answer and `null` confidence rule: Tasks 3 and 5.
- Streaming (native for `scuti`, emulated otherwise, pre-flight HTTP errors, error line): Tasks 7, 8, 9.
- `/api/gateways`, `/api/validate`, `/health`: Task 9. Admin page, routes, write-only secrets: Tasks 4 and 9.
- Gateways: `typesafe` (native types, per-question assets, image header, 0.9 bar, error mapping): Task 5. `ollama` (d3 mapping, default noul criteria, 503): Task 6. `scuti` (`/v1/ask`, strategy, window, 429 retry, tokens sum): Task 7.
- `images` and `types` capability flags with 422 and no upstream call: Task 8. Cache key with image hash, `stream` not in key, switch: Task 8. `max_inflight` 429 with `Retry-After`: Task 8. Tokens, 401 and 429: shared middleware, checked in Task 9.
- Out of scope respected: no strategies, no `local_only`, no MCP tools, no multipart or URL images.
- Types used across tasks: `DecisionRequest`, `GatewayResult`, `GatewayError`, `BaseGateway`, `build_gateway`, `answer_from`, `mark`, `compact`, `assets_for`, `GatewayStore.all/public/put/delete`, `DecisionService.decide/stream/gateways/test` have one definition each and the same signatures wherever they are used.
- Known risk to check in the first live run: TypeSafe's native `score` and `noul` types (spec says fall back to Legion's choice mapping for that type if one misbehaves). No test hits the real API.
