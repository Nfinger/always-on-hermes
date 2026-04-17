import json
import os
import urllib.request
from typing import Any, Dict, List


NOTION_VERSION = "2022-06-28"


def _clean_id(value: str) -> str:
    return value.replace("-", "").strip()


def _headers() -> Dict[str, str]:
    key = os.getenv("NOTION_API_KEY", "").strip()
    if not key:
        raise RuntimeError("NOTION_API_KEY is not set")
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _post(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode("utf-8"))
    for k, v in _headers().items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _paragraph(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        },
    }


def _heading(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        },
    }


def _bullets(items: List[str]) -> List[Dict[str, Any]]:
    out = []
    for item in items[:20]:
        out.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": item[:2000]}}],
                },
            }
        )
    return out


def create_interview_page(
    *,
    title: str,
    candidate_name: str,
    parent_page_id: str,
    summary: str,
    strengths: List[str],
    risks: List[str],
    recommendation: str,
    evidence_quotes: List[str],
    pending_questions: List[str],
) -> Dict[str, Any]:
    parent = _clean_id(parent_page_id)
    page_title = f"Interview – {candidate_name or 'Candidate'} – {title}"[:200]

    children: List[Dict[str, Any]] = [
        _paragraph(f"Role: {title}"),
        _paragraph(f"Candidate: {candidate_name or 'Unknown'}"),
        _paragraph(f"Recommendation: {recommendation}"),
        _heading("Summary"),
        _paragraph(summary or "No summary generated."),
        _heading("Strengths"),
        *_bullets(strengths or ["(none captured)"]),
        _heading("Risks"),
        *_bullets(risks or ["(none captured)"]),
        _heading("Evidence quotes"),
        *_bullets(evidence_quotes or ["(none captured)"]),
        _heading("Pending / follow-up questions"),
        *_bullets(pending_questions or ["(none)"]),
    ]

    payload = {
        "parent": {"page_id": parent},
        "properties": {
            "title": {
                "title": [{"type": "text", "text": {"content": page_title}}]
            }
        },
        "children": children,
    }

    return _post("https://api.notion.com/v1/pages", payload)
