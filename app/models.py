from typing import List, Optional
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str
    candidate_name: Optional[str] = None
    job_description: str = ""
    rubric: List[str] = Field(default_factory=list)
    mode: str = Field(default="interview", description="interview|meeting|general")
    context_notes: List[str] = Field(default_factory=list)


class TranscriptChunkIn(BaseModel):
    speaker: str = Field(description="interviewer|candidate|other")
    text: str
    ts: Optional[str] = None


class AudioChunkIn(BaseModel):
    speaker: str = Field(default="other", description="user|other|assistant")
    audio_base64: str = Field(description="Base64 encoded audio bytes from MediaRecorder")
    mime_type: str = Field(default="audio/webm", description="audio/webm|audio/wav|audio/mp4")


class AudioChunkOut(BaseModel):
    ok: bool
    accepted: bool = False
    text: str = ""
    chunk_count: int
    reason: Optional[str] = None


class RuntimeStateIn(BaseModel):
    muted: bool


class RuntimeStateOut(BaseModel):
    muted: bool


class SuggestionRequest(BaseModel):
    max_questions: int = 3


class SuggestionOut(BaseModel):
    questions: List[str]
    missing_signals: List[str] = Field(default_factory=list)


class AmbientSuggestionOut(BaseModel):
    suggestions: List[str]
    actions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class SessionOut(BaseModel):
    session_id: str
    title: str
    candidate_name: Optional[str] = None
    mode: str = "interview"
    chunk_count: int


class SummaryOut(BaseModel):
    session_id: str
    summary: str
    strengths: List[str]
    risks: List[str]
    recommendation: str
    evidence_quotes: List[str]


class NotionSyncRequest(BaseModel):
    parent_page_id: Optional[str] = None


class NotionSyncOut(BaseModel):
    ok: bool
    page_id: Optional[str] = None
    page_url: Optional[str] = None
