import base64

from fastapi.testclient import TestClient

from app.main import app
from app.store import store


def _create_session(client: TestClient) -> str:
    res = client.post(
        "/sessions",
        json={
            "title": "Audio Session",
            "mode": "general",
            "job_description": "",
            "rubric": [],
            "context_notes": [],
        },
    )
    assert res.status_code == 200
    return res.json()["session_id"]


def test_audio_chunk_transcribes_and_appends(monkeypatch):
    client = TestClient(app)
    store.reset_for_tests()
    sid = _create_session(client)

    monkeypatch.setattr("app.main.transcribe_audio_chunk", lambda *_args, **_kwargs: "ship it")

    payload = {
        "speaker": "other",
        "mime_type": "audio/webm",
        "audio_base64": base64.b64encode(b"fake-bytes").decode("utf-8"),
    }
    res = client.post(f"/sessions/{sid}/audio-chunk", json=payload)

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["accepted"] is True
    assert body["text"] == "ship it"
    assert body["chunk_count"] == 1
    assert store.get_session(sid).chunks[-1].text == "ship it"


def test_audio_chunk_drops_empty_transcript(monkeypatch):
    client = TestClient(app)
    store.reset_for_tests()
    sid = _create_session(client)

    monkeypatch.setattr("app.main.transcribe_audio_chunk", lambda *_args, **_kwargs: "   ")

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
    assert body["chunk_count"] == 0
    assert store.get_session(sid).chunks == []
