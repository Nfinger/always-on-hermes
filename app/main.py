import base64
import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from .models import (
    SessionCreate,
    TranscriptChunkIn,
    AudioChunkIn,
    AudioChunkOut,
    RuntimeStateIn,
    RuntimeStateOut,
    SuggestionRequest,
    SuggestionOut,
    AmbientSuggestionOut,
    SessionOut,
    SummaryOut,
    NotionSyncRequest,
    NotionSyncOut,
)
from .store import store
from .llm import (
    suggest_questions,
    suggest_ambient_assistance,
    summarize_interview,
    transcribe_audio_chunk,
)
from .notion import create_interview_page

app = FastAPI(title="Always-On Hermes API", version="0.2.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/runtime-state", response_model=RuntimeStateOut)
def get_runtime_state():
    return RuntimeStateOut(muted=store.get_muted())


@app.post("/runtime-state", response_model=RuntimeStateOut)
def set_runtime_state(payload: RuntimeStateIn):
    return RuntimeStateOut(muted=store.set_muted(payload.muted))


@app.get("/panel", response_class=HTMLResponse)
def panel():
    return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Always-On Hermes Panel</title>
  <style>
    body { font-family: -apple-system, system-ui, Segoe UI, sans-serif; margin: 20px; max-width: 900px; }
    .row { display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap: wrap; }
    input, select, textarea, button { font-size: 14px; padding: 8px; }
    input, select, textarea { border:1px solid #ccc; border-radius:8px; }
    button { border:0; border-radius:8px; background:#111; color:#fff; cursor:pointer; }
    button.secondary { background:#666; }
    textarea { width:100%; min-height:86px; }
    .box { border:1px solid #e5e5e5; border-radius:12px; padding:12px; margin:10px 0; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; }
    .muted { color:#666; }
  </style>
</head>
<body>
  <h2>Always-On Hermes — Shoulder Panel</h2>
  <div class=\"muted\">Runs against local API at <code>/sessions</code>. Keep this tab open.</div>

  <div class=\"box\">
    <div class=\"row\">
      <label>Title <input id=\"title\" value=\"Always-on session\" /></label>
      <label>Mode
        <select id=\"mode\">
          <option value=\"general\" selected>general</option>
          <option value=\"meeting\">meeting</option>
          <option value=\"interview\">interview</option>
        </select>
      </label>
      <label>Context notes <input id=\"notes\" value=\"always on assistant, Nate\" size=\"36\" /></label>
      <button onclick=\"startSession()\">Start Session</button>
    </div>
    <div class=\"row\">
      <span>Session:</span> <code id=\"sessionId\">(none)</code>
      <button class=\"secondary\" onclick=\"syncNotion()\">Sync Notion</button>
      <label>Parent page id <input id=\"parent\" value=\"342ca918aa048096bb08fccef2a94c49\" size=\"34\"/></label>
    </div>
    <div class=\"row\">
      <button class=\"secondary\" onclick=\"toggleMute()\">Toggle Privacy Mute</button>
      <span id=\"muteStatus\" class=\"muted\">Privacy: unknown</span>
      <span class=\"muted\">Hotkey in panel: Ctrl+Shift+M</span>
    </div>
  </div>

  <div class=\"box\">
    <div class=\"row\">
      <label>Speaker
        <select id=\"speaker\">
          <option value=\"user\">user</option>
          <option value=\"other\" selected>other</option>
          <option value=\"assistant\">assistant</option>
        </select>
      </label>
      <button onclick=\"sendChunk()\">Send Chunk</button>
      <button class=\"secondary\" onclick=\"quickChunk('Need a deeper follow-up here.')\">Quick: ask deeper</button>
      <button class=\"secondary\" onclick=\"quickChunk('Important point flagged.')\">Quick: mark important</button>
    </div>
    <div class=\"row\">
      <button onclick=\"startMicCapture()\">Start Mic Auto</button>
      <button class=\"secondary\" onclick=\"stopMicCapture()\">Stop Mic Auto</button>
      <label>Chunk seconds <input id=\"chunkSec\" value=\"3\" size=\"4\" /></label>
      <span class=\"muted\" id=\"micStatus\">Mic: idle</span>
    </div>
    <div class=\"row\">
      <label><input type=\"checkbox\" id=\"pttMode\" /> Push-to-talk mode</label>
      <span class=\"muted\">Hold Space (outside text fields) to capture audio</span>
    </div>
    <textarea id=\"chunk\" placeholder=\"Paste live transcript lines here...\"></textarea>
  </div>

  <div class=\"box\">
    <div class=\"row\">
      <button onclick=\"fetchAmbient()\">Refresh Suggestions</button>
      <label><input type=\"checkbox\" id=\"autopoll\" checked onchange=\"togglePoll()\" /> Auto-poll every 6s</label>
    </div>
    <div id=\"ambient\" class=\"mono\">No suggestions yet.</div>
  </div>

  <div class=\"box\">
    <div class=\"muted\">Event log</div>
    <div id=\"log\" class=\"mono\"></div>
  </div>

  <script>
    let sessionId = null;
    let pollHandle = null;
    let micStream = null;
    let mediaRecorder = null;
    let pttActive = false;

    function log(msg){
      const el = document.getElementById('log');
      const now = new Date().toLocaleTimeString();
      el.textContent += `[${now}] ${msg}\n`;
      el.scrollTop = el.scrollHeight;
    }

    async function api(path, method='GET', body=null){
      const opts = { method, headers: {} };
      if(body){ opts.body = JSON.stringify(body); opts.headers['content-type']='application/json'; }
      const r = await fetch(path, opts);
      const txt = await r.text();
      let data = {};
      try { data = JSON.parse(txt); } catch { data = { raw: txt }; }
      if(!r.ok) throw new Error(data.detail || txt || `HTTP ${r.status}`);
      return data;
    }

    async function refreshMute(){
      const out = await api('/runtime-state', 'GET');
      document.getElementById('muteStatus').textContent = out.muted ? 'Privacy: MUTED' : 'Privacy: live';
      return out.muted;
    }

    function playCue(kind){
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = kind === 'mute_on' ? 220 : 880;
        gain.gain.value = 0.02;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.11);
      } catch (_) {}
    }

    async function toggleMute(){
      const out = await api('/runtime-state', 'GET');
      const next = !out.muted;
      const res = await api('/runtime-state', 'POST', { muted: next });
      document.getElementById('muteStatus').textContent = res.muted ? 'Privacy: MUTED' : 'Privacy: live';
      log(`privacy mute: ${res.muted ? 'ON' : 'OFF'}`);
      playCue(res.muted ? 'mute_on' : 'mute_off');
      if(res.muted){
        stopMicCapture();
        releaseMicStream();
      }
    }

    async function startSession(){
      const title = document.getElementById('title').value.trim() || 'Always-on session';
      const mode = document.getElementById('mode').value;
      const notes = document.getElementById('notes').value.split(',').map(s => s.trim()).filter(Boolean);
      const out = await api('/sessions', 'POST', { title, mode, job_description:'', rubric:[], context_notes:notes });
      sessionId = out.session_id;
      document.getElementById('sessionId').textContent = sessionId;
      log(`session started: ${sessionId} (${mode})`);
      if(document.getElementById('autopoll').checked) startPoll();
    }

    async function sendChunk(){
      if(!sessionId){ alert('Start a session first'); return; }
      const text = document.getElementById('chunk').value.trim();
      if(!text) return;
      const speaker = document.getElementById('speaker').value;
      await api(`/sessions/${sessionId}/chunks`, 'POST', { speaker, text });
      log(`chunk sent (${speaker}): ${text.slice(0, 90)}`);
      document.getElementById('chunk').value = '';
      await fetchAmbient();
    }

    function quickChunk(text){ document.getElementById('chunk').value = text; sendChunk(); }

    async function sendAudioBlob(blob){
      if(!sessionId) return;
      const speaker = document.getElementById('speaker').value;
      const arr = new Uint8Array(await blob.arrayBuffer());
      let binary = '';
      const chunkSize = 0x8000;
      for(let i=0; i<arr.length; i += chunkSize){
        binary += String.fromCharCode.apply(null, arr.subarray(i, i + chunkSize));
      }
      const audio_base64 = btoa(binary);
      const out = await api(`/sessions/${sessionId}/audio-chunk`, 'POST', {
        speaker,
        mime_type: blob.type || 'audio/webm',
        audio_base64,
      });
      if(out.accepted && out.text){
        log(`mic chunk (${speaker}): ${out.text.slice(0, 90)}`);
        await fetchAmbient();
      } else if(out.reason){
        log(`mic chunk skipped: ${out.reason}`);
      }
    }

    function pttEnabled(){
      return !!document.getElementById('pttMode').checked;
    }

    async function ensureMicStream(){
      if(micStream) return;
      if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
        throw new Error('Mic capture not supported in this browser');
      }
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }

    function releaseMicStream(){
      if(micStream){
        micStream.getTracks().forEach(t => t.stop());
        micStream = null;
      }
    }

    async function startMicCapture(){
      if(!sessionId){ alert('Start a session first'); return; }
      if(mediaRecorder && mediaRecorder.state !== 'inactive') return;
      const muted = await refreshMute();
      if(muted){ alert('Privacy mute is ON. Toggle mute off to start mic.'); return; }
      await ensureMicStream();

      const baseSec = Math.max(1, parseInt(document.getElementById('chunkSec').value || '3', 10));
      const sec = pttEnabled() ? 1 : baseSec;
      mediaRecorder = new MediaRecorder(micStream, { mimeType: 'audio/webm' });
      mediaRecorder.ondataavailable = async (ev) => {
        if(ev.data && ev.data.size > 0){
          try { await sendAudioBlob(ev.data); }
          catch(err){ log('mic send error: ' + err.message); }
        }
      };
      mediaRecorder.onstart = () => {
        document.getElementById('micStatus').textContent = pttEnabled() ? 'Mic: PTT recording' : 'Mic: recording';
        log(`mic started (chunk every ${sec}s)`);
      };
      mediaRecorder.onstop = () => {
        document.getElementById('micStatus').textContent = pttEnabled() ? 'Mic: armed (PTT)' : 'Mic: idle';
        log('mic stopped');
      };
      mediaRecorder.start(sec * 1000);
    }

    function stopMicCapture(){
      if(mediaRecorder && mediaRecorder.state !== 'inactive'){
        try { mediaRecorder.requestData(); } catch(_) {}
        mediaRecorder.stop();
      }
      if(!pttEnabled()){
        releaseMicStream();
      }
      mediaRecorder = null;
      document.getElementById('micStatus').textContent = pttEnabled() ? 'Mic: armed (PTT)' : 'Mic: idle';
    }

    function canUsePttKey(ev){
      if(ev.code !== 'Space') return false;
      const el = document.activeElement;
      const tag = (el && el.tagName || '').toLowerCase();
      if(tag === 'input' || tag === 'textarea' || (el && el.isContentEditable)) return false;
      return document.getElementById('pttMode').checked;
    }

    async function startPushToTalk(){
      if(pttActive) return;
      pttActive = true;
      try { await startMicCapture(); }
      catch(e){ log('ptt start error: ' + e.message); pttActive = false; }
    }

    function stopPushToTalk(){
      if(!pttActive) return;
      pttActive = false;
      stopMicCapture();
    }

    async function fetchAmbient(){
      if(!sessionId) return;
      const out = await api(`/sessions/${sessionId}/ambient-suggestions`, 'POST', { max_questions: 3 });
      const lines = [];
      lines.push('Suggestions:');
      (out.suggestions || []).forEach((s,i)=>lines.push(`${i+1}. ${s}`));
      if((out.actions||[]).length){
        lines.push('\nActions:');
        out.actions.forEach(a=>lines.push(`- ${a}`));
      }
      if((out.risks||[]).length){
        lines.push('\nRisks:');
        out.risks.forEach(r=>lines.push(`- ${r}`));
      }
      document.getElementById('ambient').textContent = lines.join('\n');
    }

    async function syncNotion(){
      if(!sessionId){ alert('Start a session first'); return; }
      const parent_page_id = document.getElementById('parent').value.trim();
      const out = await api(`/sessions/${sessionId}/notion-sync`, 'POST', { parent_page_id });
      log(`notion synced: ${out.page_url || out.page_id}`);
    }

    function startPoll(){
      if(pollHandle) clearInterval(pollHandle);
      pollHandle = setInterval(()=>{ fetchAmbient().catch(e => log('poll error: '+e.message)); }, 6000);
    }

    function stopPoll(){
      if(pollHandle) clearInterval(pollHandle);
      pollHandle = null;
    }

    function togglePoll(){
      if(document.getElementById('autopoll').checked) startPoll(); else stopPoll();
    }

    document.addEventListener('keydown', (ev) => {
      if(ev.ctrlKey && ev.shiftKey && (ev.key === 'M' || ev.key === 'm')){
        ev.preventDefault();
        toggleMute().catch(e => log('mute toggle error: ' + e.message));
        return;
      }
      if(canUsePttKey(ev) && !ev.repeat){
        ev.preventDefault();
        startPushToTalk();
      }
    });

    document.addEventListener('keyup', (ev) => {
      if(canUsePttKey(ev)){
        ev.preventDefault();
        stopPushToTalk();
      }
    });

    window.addEventListener('blur', () => stopPushToTalk());

    document.getElementById('pttMode').addEventListener('change', async (ev) => {
      if(ev.target.checked){
        try {
          await ensureMicStream();
          document.getElementById('micStatus').textContent = 'Mic: armed (PTT)';
          log('ptt armed: mic pre-warmed for faster first-word pickup');
        } catch (e) {
          log('ptt arm error: ' + e.message);
        }
      } else {
        stopPushToTalk();
        releaseMicStream();
        document.getElementById('micStatus').textContent = 'Mic: idle';
        log('ptt disabled: released mic pre-warm stream');
      }
    });

    refreshMute().catch(e => log('mute refresh error: ' + e.message));
    startPoll();
  </script>
</body>
</html>
"""


def _transcript_for_session(session_id: str):
    chunks = store.get_chunks(session_id)
    return [{"speaker": c.speaker, "text": c.text, "ts": c.ts} for c in chunks]


def _ambient_payload_for_session(session_id: str, max_suggestions: int):
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    transcript = _transcript_for_session(session_id)
    out = suggest_ambient_assistance(
        mode=s.mode,
        context_notes=s.context_notes,
        transcript=transcript,
        max_suggestions=max_suggestions,
    )
    return AmbientSuggestionOut(
        suggestions=out.get("suggestions", [])[:max_suggestions],
        actions=out.get("actions", []),
        risks=out.get("risks", []),
    )


@app.post("/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate):
    s = store.create_session(
        title=payload.title,
        candidate_name=payload.candidate_name,
        job_description=payload.job_description,
        rubric=payload.rubric,
        mode=payload.mode,
        context_notes=payload.context_notes,
    )
    return SessionOut(
        session_id=s.session_id,
        title=s.title,
        candidate_name=s.candidate_name,
        mode=s.mode,
        chunk_count=store.chunk_count(s.session_id),
    )


@app.post("/sessions/{session_id}/chunks")
def add_chunk(session_id: str, payload: TranscriptChunkIn):
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    count = store.add_chunk(session_id, payload.speaker, payload.text, payload.ts)
    return {"ok": True, "chunk_count": count}


@app.post("/sessions/{session_id}/audio-chunk", response_model=AudioChunkOut)
def add_audio_chunk(session_id: str, payload: AudioChunkIn):
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        audio_bytes = base64.b64decode(payload.audio_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="audio_base64 must be valid base64")

    if store.get_muted():
        return AudioChunkOut(
            ok=True,
            accepted=False,
            text="",
            chunk_count=store.chunk_count(session_id),
            reason="privacy_muted",
        )

    try:
        text = transcribe_audio_chunk(audio_bytes=audio_bytes, mime_type=payload.mime_type).strip()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Audio transcription failed: {e}")

    if not text:
        return AudioChunkOut(
            ok=True,
            accepted=False,
            text="",
            chunk_count=store.chunk_count(session_id),
            reason="empty_transcript",
        )

    count = store.add_chunk(session_id, payload.speaker, text, None)
    return AudioChunkOut(ok=True, accepted=True, text=text, chunk_count=count, reason=None)


@app.post("/sessions/{session_id}/suggestions", response_model=SuggestionOut)
def get_suggestions(session_id: str, payload: SuggestionRequest):
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    transcript = _transcript_for_session(session_id)
    try:
        out = suggest_questions(
            job_description=s.job_description,
            rubric=s.rubric,
            transcript=transcript,
            max_questions=payload.max_questions,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Suggestion generation failed: {e}")

    return SuggestionOut(
        questions=out.get("questions", [])[: payload.max_questions],
        missing_signals=out.get("missing_signals", []),
    )


@app.post("/sessions/{session_id}/ambient-suggestions", response_model=AmbientSuggestionOut)
def get_ambient_suggestions(session_id: str, payload: SuggestionRequest):
    try:
        return _ambient_payload_for_session(session_id, payload.max_questions)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ambient suggestion generation failed: {e}")


@app.websocket("/sessions/{session_id}/stream")
async def session_stream(session_id: str, websocket: WebSocket):
    s = store.get_session(session_id)
    if not s:
        await websocket.close(code=4404, reason="session not found")
        return

    await websocket.accept()
    await websocket.send_json({"type": "ready", "session_id": session_id})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "invalid json"})
                continue

            msg_type = (msg.get("type") or "").strip().lower()
            if msg_type == "chunk":
                speaker = (msg.get("speaker") or "other").strip() or "other"
                text = (msg.get("text") or "").strip()
                if not text:
                    await websocket.send_json({"type": "error", "detail": "empty chunk text"})
                    continue
                count = store.add_chunk(session_id, speaker, text, msg.get("ts"))
                ambient = _ambient_payload_for_session(session_id, int(msg.get("max_questions", 3)))
                await websocket.send_json(
                    {
                        "type": "update",
                        "chunk_count": count,
                        "suggestions": ambient.suggestions,
                        "actions": ambient.actions,
                        "risks": ambient.risks,
                    }
                )
            elif msg_type == "ambient":
                ambient = _ambient_payload_for_session(session_id, int(msg.get("max_questions", 3)))
                await websocket.send_json(
                    {
                        "type": "ambient",
                        "suggestions": ambient.suggestions,
                        "actions": ambient.actions,
                        "risks": ambient.risks,
                    }
                )
            else:
                await websocket.send_json({"type": "error", "detail": "unsupported message type"})
    except WebSocketDisconnect:
        return


def _session_summary(session_id: str) -> SummaryOut:
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    transcript = _transcript_for_session(session_id)
    try:
        out = summarize_interview(s.job_description, s.rubric, transcript)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Summary generation failed: {e}")
    return SummaryOut(
        session_id=session_id,
        summary=out.get("summary", ""),
        strengths=out.get("strengths", []),
        risks=out.get("risks", []),
        recommendation=out.get("recommendation", "lean_no"),
        evidence_quotes=out.get("evidence_quotes", []),
    )


@app.get("/sessions/{session_id}/summary", response_model=SummaryOut)
def get_summary(session_id: str):
    return _session_summary(session_id)


@app.post("/sessions/{session_id}/notion-sync", response_model=NotionSyncOut)
def sync_to_notion(session_id: str, payload: NotionSyncRequest):
    s = store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    parent_page_id = payload.parent_page_id
    if not parent_page_id:
        import os

        parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID", "").strip()
    if not parent_page_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Notion parent page id. Provide parent_page_id in request or set NOTION_PARENT_PAGE_ID.",
        )

    summary = _session_summary(session_id)

    transcript = _transcript_for_session(session_id)
    try:
        suggestions = suggest_questions(
            job_description=s.job_description,
            rubric=s.rubric,
            transcript=transcript,
            max_questions=5,
        )
        pending_questions = suggestions.get("questions", [])
    except Exception:
        pending_questions = []

    try:
        notion_page = create_interview_page(
            title=s.title,
            candidate_name=s.candidate_name or "",
            parent_page_id=parent_page_id,
            summary=summary.summary,
            strengths=summary.strengths,
            risks=summary.risks,
            recommendation=summary.recommendation,
            evidence_quotes=summary.evidence_quotes,
            pending_questions=pending_questions,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notion sync failed: {e}")

    return NotionSyncOut(
        ok=True,
        page_id=notion_page.get("id"),
        page_url=notion_page.get("url"),
    )
