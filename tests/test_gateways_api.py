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
