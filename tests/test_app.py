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
    if str(request.url).endswith("/health"):
        return httpx.Response(200, json={"ready": True})
    body = json.loads(request.content)
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
