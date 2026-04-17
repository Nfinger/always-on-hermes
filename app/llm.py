import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Prefer local project .env, then fall back to Hermes global .env
load_dotenv()
load_dotenv(Path.home() / ".hermes" / ".env", override=False)


def _api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def _client() -> OpenAI:
    return OpenAI(
        api_key=_api_key(),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )


def _model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def _heuristic_questions(rubric: list[str], transcript: list[dict], max_questions: int) -> dict:
    recent = " ".join([(x.get("text") or "") for x in transcript[-3:]])
    questions = []
    if "ownership" in [r.lower() for r in rubric]:
        questions.append("Can you walk me through a decision you owned end-to-end, including tradeoffs?")
    if "system design" in [r.lower() for r in rubric]:
        questions.append("How would you design this for scale and failure recovery?")
    if "communication" in [r.lower() for r in rubric]:
        questions.append("How did you align stakeholders when there was disagreement?")
    if "incident" in recent.lower():
        questions.append("What was your exact role during the incident and what did you change afterward?")
    if not questions:
        questions = [
            "What is the most complex problem you solved recently and why was it hard?",
            "What would your former manager say is your biggest strength and your biggest growth area?",
        ]
    return {"questions": questions[:max_questions], "missing_signals": rubric[:3]}


def suggest_questions(job_description: str, rubric: list[str], transcript: list[dict], max_questions: int) -> dict:
    if not _api_key():
        return _heuristic_questions(rubric, transcript, max_questions)

    system_prompt = os.getenv(
        "SYSTEM_PROMPT",
        "You are an interview copilot. Output compact JSON only.",
    )
    user_prompt = {
        "task": "Generate follow-up interview questions.",
        "max_questions": max_questions,
        "job_description": job_description,
        "rubric": rubric,
        "recent_transcript": transcript[-20:],
        "output_schema": {
            "questions": ["string"],
            "missing_signals": ["string"],
        },
    }

    resp = _client().chat.completions.create(
        model=_model(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt)},
        ],
    )
    txt = resp.choices[0].message.content or "{}"
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return {"questions": [txt.strip()], "missing_signals": []}


def suggest_ambient_assistance(
    mode: str,
    context_notes: list[str],
    transcript: list[dict],
    max_suggestions: int = 3,
) -> dict:
    recent = transcript[-20:]
    if not _api_key():
        text = " ".join([(x.get("text") or "") for x in recent]).lower()
        suggestions = [
            "Summarize what was just decided in one sentence.",
            "Ask one clarifying question to remove ambiguity.",
            "Capture concrete next steps with owners and dates.",
        ]
        actions = []
        risks = []
        if any(k in text for k in ["later", "soon", "eventually", "maybe"]):
            risks.append("Ambiguous timing detected; convert to a specific deadline.")
        if "i'll" in text or "we will" in text:
            actions.append("Convert verbal commitments into explicit tasks.")
        if mode == "interview":
            suggestions.insert(0, "Probe for ownership and measurable outcomes.")
        return {
            "suggestions": suggestions[:max_suggestions],
            "actions": actions[:max_suggestions],
            "risks": risks[:max_suggestions],
        }

    prompt = {
        "task": "Provide proactive shoulder-assistant guidance from live context.",
        "mode": mode,
        "context_notes": context_notes,
        "recent_transcript": recent,
        "max_suggestions": max_suggestions,
        "output_schema": {
            "suggestions": ["string"],
            "actions": ["string"],
            "risks": ["string"],
        },
    }
    resp = _client().chat.completions.create(
        model=_model(),
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "You are an always-on shoulder assistant. Return compact JSON only.",
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    txt = resp.choices[0].message.content or "{}"
    try:
        out = json.loads(txt)
        return {
            "suggestions": (out.get("suggestions") or [])[:max_suggestions],
            "actions": (out.get("actions") or [])[:max_suggestions],
            "risks": (out.get("risks") or [])[:max_suggestions],
        }
    except json.JSONDecodeError:
        return {"suggestions": [txt.strip()], "actions": [], "risks": []}


_WHISPER_MODEL = None


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    from faster_whisper import WhisperModel

    size = os.getenv("WHISPER_MODEL_SIZE", "base.en")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    model_dir = os.getenv("WHISPER_MODEL_DIR", "").strip() or None
    _WHISPER_MODEL = WhisperModel(
        size,
        device=device,
        compute_type=compute_type,
        download_root=model_dir,
    )
    return _WHISPER_MODEL


def _transcribe_with_whisper_local(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    import tempfile

    ext_map = {
        "audio/webm": ".webm",
        "audio/wav": ".wav",
        "audio/mp4": ".mp4",
        "audio/mpeg": ".mp3",
    }
    suffix = ext_map.get((mime_type or "").lower(), ".webm")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        model = _get_whisper_model()
        language = os.getenv("WHISPER_LANGUAGE", "en")
        segments, _info = model.transcribe(
            tmp_path,
            language=language,
            vad_filter=True,
            beam_size=1,
        )
        parts = []
        for seg in segments:
            txt = (seg.text or "").strip()
            if txt:
                parts.append(txt)
        return " ".join(parts).strip()
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def transcribe_audio_chunk(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    if not audio_bytes:
        return ""

    provider = os.getenv("STT_PROVIDER", "whisper_local").strip().lower()
    allowed = {"whisper_local", "faster_whisper", "whisper"}
    if provider not in allowed:
        raise ValueError(
            f"Unsupported STT_PROVIDER='{provider}'. This app is locked to local open-source Whisper (use STT_PROVIDER=whisper_local)."
        )
    return _transcribe_with_whisper_local(audio_bytes=audio_bytes, mime_type=mime_type)


def summarize_interview(job_description: str, rubric: list[str], transcript: list[dict]) -> dict:
    if not _api_key():
        snippets = [f"{x.get('speaker','?')}: {x.get('text','')}" for x in transcript[-8:]]
        return {
            "summary": "Heuristic summary (no LLM key configured).",
            "strengths": ["Demonstrated relevant experience"],
            "risks": ["Need deeper evidence across rubric dimensions"],
            "recommendation": "lean_yes" if transcript else "lean_no",
            "evidence_quotes": snippets[:5],
        }

    prompt = {
        "task": "Summarize interview and produce recommendation.",
        "job_description": job_description,
        "rubric": rubric,
        "transcript": transcript,
        "output_schema": {
            "summary": "string",
            "strengths": ["string"],
            "risks": ["string"],
            "recommendation": "strong_yes|yes|lean_yes|lean_no|no|strong_no",
            "evidence_quotes": ["string"],
        },
    }
    resp = _client().chat.completions.create(
        model=_model(),
        temperature=0.1,
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    txt = resp.choices[0].message.content or "{}"
    return json.loads(txt)
