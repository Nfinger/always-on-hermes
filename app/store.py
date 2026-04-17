import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> Path:
    env = os.getenv("SHOULDER_DB_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parents[1] / "data" / "always_on_hermes.db"


@dataclass
class Chunk:
    speaker: str
    text: str
    ts: Optional[str] = None


@dataclass
class Session:
    session_id: str
    title: str
    candidate_name: Optional[str]
    job_description: str
    rubric: List[str] = field(default_factory=list)
    mode: str = "interview"
    context_notes: List[str] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)


class SQLiteStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = (db_path or _default_db_path()).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    candidate_name TEXT,
                    job_description TEXT NOT NULL,
                    rubric_json TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    context_notes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    text TEXT NOT NULL,
                    ts TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO runtime_state (key, value) VALUES ('muted', 'false')"
            )
            conn.commit()

    def create_session(
        self,
        title: str,
        candidate_name: Optional[str],
        job_description: str,
        rubric: List[str],
        mode: str = "interview",
        context_notes: Optional[List[str]] = None,
    ) -> Session:
        sid = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, title, candidate_name, job_description,
                    rubric_json, mode, context_notes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    title,
                    candidate_name,
                    job_description,
                    json.dumps(rubric or []),
                    mode,
                    json.dumps(context_notes or []),
                    _utcnow(),
                ),
            )
            conn.commit()
        return Session(
            session_id=sid,
            title=title,
            candidate_name=candidate_name,
            job_description=job_description,
            rubric=rubric or [],
            mode=mode,
            context_notes=context_notes or [],
            chunks=[],
        )

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None

            chunks = self.get_chunks(session_id, conn=conn)
            return Session(
                session_id=row["session_id"],
                title=row["title"],
                candidate_name=row["candidate_name"],
                job_description=row["job_description"],
                rubric=json.loads(row["rubric_json"] or "[]"),
                mode=row["mode"],
                context_notes=json.loads(row["context_notes_json"] or "[]"),
                chunks=chunks,
            )

    def get_chunks(self, session_id: str, conn: Optional[sqlite3.Connection] = None) -> List[Chunk]:
        owns_conn = conn is None
        conn = conn or self._connect()
        try:
            rows = conn.execute(
                "SELECT speaker, text, ts FROM chunks WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [Chunk(speaker=r["speaker"], text=r["text"], ts=r["ts"]) for r in rows]
        finally:
            if owns_conn:
                conn.close()

    def add_chunk(self, session_id: str, speaker: str, text: str, ts: Optional[str] = None) -> int:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chunks (session_id, speaker, text, ts, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, speaker, text, ts, _utcnow()),
            )
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM chunks WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            conn.commit()
            return int(row["c"])

    def chunk_count(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM chunks WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return int(row["c"])

    def get_muted(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM runtime_state WHERE key = 'muted'"
            ).fetchone()
            return (row["value"] if row else "false").lower() == "true"

    def set_muted(self, muted: bool) -> bool:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runtime_state (key, value) VALUES ('muted', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("true" if muted else "false",),
            )
            conn.commit()
        return muted

    def reset_for_tests(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM runtime_state WHERE key='muted'")
            conn.execute("INSERT INTO runtime_state (key, value) VALUES ('muted', 'false')")
            conn.commit()


store = SQLiteStore()
