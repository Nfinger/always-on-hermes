import importlib


def test_transcribe_uses_whisper_local_by_default(monkeypatch):
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm = importlib.import_module("app.llm")

    called = {"local": 0}

    def fake_local(audio_bytes, mime_type):
        called["local"] += 1
        return "local transcript"

    monkeypatch.setattr(llm, "_transcribe_with_whisper_local", fake_local)

    out = llm.transcribe_audio_chunk(b"123", "audio/webm")
    assert out == "local transcript"
    assert called["local"] == 1


def test_transcribe_rejects_paid_provider_values(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "openai")

    llm = importlib.import_module("app.llm")

    monkeypatch.setattr(llm, "_transcribe_with_whisper_local", lambda *_args, **_kwargs: "local transcript")

    try:
        llm.transcribe_audio_chunk(b"123", "audio/webm")
        assert False, "expected ValueError for paid provider"
    except ValueError as e:
        assert "whisper_local" in str(e)
