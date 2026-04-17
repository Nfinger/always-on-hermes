import json

from fastapi.testclient import TestClient

from app.main import app
from app.store import store


def _create_session(client: TestClient) -> str:
    res = client.post(
        "/sessions",
        json={
            "title": "WS Session",
            "mode": "general",
            "job_description": "",
            "rubric": [],
            "context_notes": [],
        },
    )
    assert res.status_code == 200
    return res.json()["session_id"]


def test_websocket_chunk_stream_updates(monkeypatch):
    client = TestClient(app)
    store.reset_for_tests()
    sid = _create_session(client)

    monkeypatch.setattr(
        "app.main.suggest_ambient_assistance",
        lambda **_kwargs: {"suggestions": ["Clarify owner"], "actions": ["Create task"], "risks": []},
    )

    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        ws.send_text(json.dumps({"type": "chunk", "speaker": "other", "text": "We should ship Friday"}))
        update = ws.receive_json()
        assert update["type"] == "update"
        assert update["chunk_count"] == 1
        assert update["suggestions"] == ["Clarify owner"]
