import base64

from fastapi.testclient import TestClient

from app.main import app
from app.store import store


def _create_session(client: TestClient) -> str:
    res = client.post(
        "/sessions",
        json={
            "title": "Runtime State Session",
            "mode": "general",
            "job_description": "",
            "rubric": [],
            "context_notes": [],
        },
    )
    assert res.status_code == 200
    return res.json()["session_id"]


def test_runtime_state_toggle():
    client = TestClient(app)
    store.reset_for_tests()

    res = client.get("/runtime-state")
    assert res.status_code == 200
    assert res.json() == {"muted": False}

    res = client.post("/runtime-state", json={"muted": True})
    assert res.status_code == 200
    assert res.json() == {"muted": True}

    res = client.get("/runtime-state")
    assert res.status_code == 200
    assert res.json() == {"muted": True}


def test_audio_chunk_blocked_when_privacy_muted(monkeypatch):
    client = TestClient(app)
    store.reset_for_tests()
    store.set_muted(True)
    sid = _create_session(client)

    monkeypatch.setattr("app.main.transcribe_audio_chunk", lambda *_args, **_kwargs: "should never run")

    payload = {
        "speaker": "other",
        "mime_type": "audio/webm",
        "audio_base64": base64.b64encode(b"fake-bytes").decode("utf-8"),
    }
    res = client.post(f"/sessions/{sid}/audio-chunk", json=payload)

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["accepted"] is False
    assert body["reason"] == "privacy_muted"
    assert body["chunk_count"] == 0
    store.set_muted(False)
