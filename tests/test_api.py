import pytest
from fastapi.testclient import TestClient

from app.main import app

KEY = {"X-API-Key": "test-key"}
GOOD_SCAN = {
    "robot_id": "k9x-01",
    "shipping_id": "LK-2026-000101",
    "sender": "Ceylon Tea Exports Ltd, Colombo",
    "receiver": "Harrods Food Hall, London",
    "destination": "London, UK",
    "weight_kg": 12.5,
    "hazard_labels": [],
    "ocr_confidence": 0.97,
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_requires_api_key(client):
    assert client.post("/api/scan", json=GOOD_SCAN).status_code == 401
    assert client.post("/api/scan", json=GOOD_SCAN, headers={"X-API-Key": "wrong"}).status_code == 401


def test_matching_scan(client):
    r = client.post("/api/scan", json=GOOD_SCAN, headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "MATCH"
    assert body["halt"] is False
    assert body["manifest_source"] == "mock"


def test_unknown_shipping_id(client):
    r = client.post("/api/scan", json={**GOOD_SCAN, "shipping_id": "XX-0000"}, headers=KEY)
    assert r.json()["status"] == "NOT_FOUND"
    assert r.json()["halt"] is True


def test_ocr_misread_id_still_finds_manifest(client):
    r = client.post("/api/scan", json={**GOOD_SCAN, "shipping_id": "LK-2O26-OOO1O1"}, headers=KEY)
    assert r.json()["status"] == "PARTIAL"
    assert r.json()["fields"][0]["status"] == "uncertain"


def test_mismatch_is_stored_and_listed(client):
    r = client.post("/api/scan", json={**GOOD_SCAN, "weight_kg": 30}, headers=KEY)
    assert r.json()["status"] == "MISMATCH"
    iid = r.json()["inspection_id"]

    detail = client.get(f"/api/inspections/{iid}").json()
    assert detail["scan"]["weight_kg"] == 30
    assert detail["manifest"]["weight_kg"] == 12.5

    listed = client.get("/api/inspections", params={"status": "mismatch"}).json()
    assert any(i["inspection_id"] == iid for i in listed)


def test_websocket_receives_new_inspection(client):
    with client.websocket_connect("/ws/live") as ws:
        client.post("/api/scan", json=GOOD_SCAN, headers=KEY)
        msg = ws.receive_json()
    assert msg["type"] == "inspection"
    assert msg["data"]["shipping_id"] == "LK-2026-000101"


def test_add_mock_manifest_record(client):
    rec = {"shipping_id": "TEST-1", "sender": "A", "receiver": "B", "destination": "C", "weight_kg": 1, "hazard_labels": []}
    assert client.post("/api/manifest/mock", json=rec, headers=KEY).status_code == 200
    assert client.get("/api/manifest/lookup/test-1", headers=KEY).json()["sender"] == "A"


def test_stats(client):
    s = client.get("/api/stats").json()
    assert s["total"] >= 3
    assert s["MATCH"] >= 1 and s["MISMATCH"] >= 1 and s["NOT_FOUND"] >= 1
