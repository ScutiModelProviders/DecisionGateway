"""Regression proof for genuine integration mistakes in the approved plan."""
import json

import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings
from src.contract import parse_request
from src.service import DecisionService
from src.store import GatewayStore
from tests.seed import seed_token

CHOICE = {"type": "choice", "instructions": "Team?", "criteria": {"a": "A", "b": "B"}}
ANSWER = {"type": "choice", "choice": "a", "answer_confidence": 0.95, "uncertain": False}


def test_admin_sign_in_settings_and_live_update(tmp_path):
    settings = seed_token(Settings(data_dir=tmp_path, admin_password="pw"))
    with TestClient(build_app(settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))) as client:
        assert client.get("/admin/settings").status_code == 401
        headers = {"X-Admin-Password": "pw"}
        assert client.get("/admin/status", headers=headers).status_code == 200
        response = client.get("/admin/settings", headers=headers)
        assert response.status_code == 200 and response.json()["service"] == "DecisionGateway"
        assert client.put("/admin/settings", headers=headers, json={"values": {"max_chars": 2, "cache": False}}).status_code == 200
        assert client.put("/admin/settings", headers=headers, json={"values": {"max_inflight": 0}}).status_code == 422
        response = client.post("/api/decide", headers={"X-Internal-Token": "tok"},
                               json={"gateway": "laya", "text": "hello", "questions": {"q": CHOICE}})
        assert response.status_code == 422 and "2 characters" in response.json()["message"]


async def test_gateway_edit_does_not_reuse_previous_models_answer(tmp_path):
    store = GatewayStore(tmp_path / "gateways.json")
    store.put("d3", {"kind": "ollama", "url": "http://model", "model": "old-model"})
    calls = []

    def handler(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        return httpx.Response(200, json={"answers": {"q": {"choice": "a", "confidence": 0.95,
                                                             "probabilities": {"a": 0.95, "b": 0.05}}}})

    service = DecisionService(store, Settings(), httpx.MockTransport(handler))
    request = parse_request({"gateway": "d3", "text": "hello", "questions": {"q": CHOICE}}, 16000)
    assert (await service.decide(request))["model"] == "old-model"
    store.put("d3", {"kind": "ollama", "model": "new-model"})
    assert (await service.decide(request))["model"] == "new-model"
    assert calls == ["old-model", "new-model"]


@pytest.mark.parametrize("partial", [False, True])
def test_truncated_upstream_stream_returns_clean_error(tmp_path, partial):
    GatewayStore(tmp_path / "gateways.json").put("laya", {"kind": "scuti", "url": "http://model"})
    settings = seed_token(Settings(data_dir=tmp_path, admin_password="pw"))
    content = (json.dumps({"type": "answer", "id": "q", "answer": ANSWER}) + "\n").encode() if partial else b""
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    with TestClient(build_app(settings, transport=transport)) as client:
        response = client.post("/api/decide", headers={"X-Internal-Token": "tok"},
                               json={"gateway": "laya", "text": "hello", "questions": {"q": CHOICE}, "stream": True})
    if partial:
        lines = [json.loads(line) for line in response.text.splitlines()]
        assert response.status_code == 200 and [line["type"] for line in lines] == ["answer", "error"]
        assert lines[-1]["status"] == 502
    else:
        assert response.status_code == 502 and response.json()["error"] == "gateway_bad_reply"
