# Always-On Hermes (MVP)

Real-time shoulder assistant (interviews + meetings + general ambient mode).

What it does now:
- Creates sessions with mode: `interview|meeting|general`
- Ingests live transcript chunks (manual text or mic auto-capture)
- Suggests interview follow-ups (`/suggestions`) or ambient guidance (`/ambient-suggestions`)
- Builds structured summary payload
- Syncs summary into Notion as a new page under a parent page

## Why this MVP
This is the smallest useful backend to prove the workflow:
1) Candidate speaks
2) Transcript chunk is sent
3) Copilot suggests follow-ups grounded in JD + rubric
4) Final summary generated for notes/Notion

Note: if no OPENAI_API_KEY is configured, the API falls back to heuristic suggestions/summaries so the pilot flow still runs.

## Tech
- FastAPI
- Pydantic
- SQLite durable session store (default DB in `data/always_on_hermes.db`)
- OpenAI-compatible chat endpoint for suggestions/summaries

## Run (manual)
```bash
cd /Users/homebase/.hermes/tools/interview-copilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set API key/model in .env
uvicorn app.main:app --reload --port 8899
```

## Run as a Mac background service (launchd)
```bash
/Users/homebase/.hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh install
/Users/homebase/.hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh status
```

Useful commands:
```bash
./scripts/hermes_shoulderctl.sh start
./scripts/hermes_shoulderctl.sh stop
./scripts/hermes_shoulderctl.sh restart
./scripts/hermes_shoulderctl.sh logs
./scripts/hermes_shoulderctl.sh test
./scripts/hermes_shoulderctl.sh ui-open

# Phase 3 companion (menu bar + mute hotkey)
./scripts/hermes_shoulderctl.sh menubar-install
./scripts/hermes_shoulderctl.sh menubar-status

# Native overlay
./scripts/hermes_shoulderctl.sh overlay-install
./scripts/hermes_shoulderctl.sh overlay-start
./scripts/hermes_shoulderctl.sh overlay-status
```

## Install on a new Mac (same repo/path copied over)
```bash
./scripts/install_local.sh
```

If installer UI hangs, bypass it and install directly:
```bash
mkdir -p ~/.hermes/tools/interview-copilot
rsync -a /usr/local/share/always-on-hermes/interview-copilot/ ~/.hermes/tools/interview-copilot/
bash ~/.hermes/tools/interview-copilot/scripts/install_local.sh
```

Python note:
- Installer script now prefers Python 3.13/3.12/3.11 and rebuilds `.venv` if it detects 3.14+
- If your machine only has Python 3.14, install still attempts ABI3 compatibility automatically

## Deploy to another Mac over SSH
```bash
./scripts/deploy_remote_mac.sh <ssh-host> [remote_dir]
# example
./scripts/deploy_remote_mac.sh nate-macbook.local ~/.hermes/tools/interview-copilot
```

## Build distributable installer package (unsigned)
```bash
./scripts/build_pkg.sh
# output: ./dist/always-on-hermes-unsigned.pkg
```

Current package behavior:
- Includes bundled `.venv` (no pip install on target machine)
- Postinstall attempts zero-touch start of backend + menubar + native overlay
- Postinstall log: `/tmp/always-on-hermes-postinstall.log`

## Sign + notarize package (optional, for clean install UX)
```bash
./scripts/sign_notarize_pkg.sh \
  ./dist/always-on-hermes-unsigned.pkg \
  "Developer ID Installer: Your Name (TEAMID)" \
  AC_PROFILE
```

Open UI + docs:
- Shoulder panel UI: http://127.0.0.1:8899/panel
- API docs: http://127.0.0.1:8899/docs

## Phase 2: Mic capture (hands-free chunks)
1) Open panel (`/panel`) and start a session
2) Click `Start Mic Auto`
3) Allow microphone permission in browser
4) Speak normally; audio chunks are sent every N seconds (default 3)
5) Suggestions refresh automatically as transcripts are added

## Phase 3: Mac companion controls
- Menu bar companion app with quick actions
  - Open Native Overlay
  - Open Web Panel (optional fallback)
  - Toggle Privacy Mute
  - Live mute status in menu bar icon/text
- Global mute hotkey (from companion): Cmd+Option+M
- Panel hotkey (focused tab): Ctrl+Shift+M
- Backend-enforced privacy mute: when muted, `/audio-chunk` refuses ingestion with `reason=privacy_muted`

## Phase 3.1: Push-to-talk + audible cues + default boot session
- Panel push-to-talk mode: enable checkbox, then hold Space (outside text fields) to capture mic
- PTT first-word optimization
  - Mic is pre-warmed when PTT is enabled (reduces first-word clipping)
  - PTT uses 1-second chunk cadence
  - Auto mode default chunk cadence tightened to 3 seconds
- Audible cue on mute toggle
  - Panel: high tone = unmuted, low tone = muted
  - Menubar: macOS beep cue on toggle
- Menubar auto-start default session on launch/login (configurable via env)
  - `AUTO_START_DEFAULT_SESSION=1`
  - `AUTO_START_SESSION_TITLE=Always-on session`
  - `AUTO_START_SESSION_NOTES=always on assistant, Nate`

Notes:
- Default STT is local open-source Whisper via `faster-whisper` (`STT_PROVIDER=whisper_local`)
- First run downloads the configured Whisper model (default `base.en`)
- Tune latency/accuracy with `WHISPER_MODEL_SIZE` (`tiny.en|base.en|small.en`)
- Paid STT providers are intentionally blocked; non-whisper STT_PROVIDER values return an error

## Core endpoints
- `POST /sessions` create session (`mode`, context, rubric)
- `POST /sessions/{id}/chunks` add transcript chunk
- `POST /sessions/{id}/audio-chunk` add mic audio chunk (base64) + transcribe + append transcript
- `POST /sessions/{id}/suggestions` interview-oriented follow-up prompts
- `POST /sessions/{id}/ambient-suggestions` always-on shoulder prompts + actions + risks
- `WS /sessions/{id}/stream` low-latency stream (send chunk messages, receive live updates)
- `GET /sessions/{id}/summary` structured summary
- `POST /sessions/{id}/notion-sync` create a Notion page with summary + strengths/risks + follow-up prompts

## Definition of done (current build)
- [x] Always-on local backend service (launchd)
- [x] Browser shoulder panel UI
- [x] Native macOS overlay UI
- [x] Open-source local STT only (whisper_local lock)
- [x] Privacy mute (UI + backend enforced)
- [x] Menubar companion
- [x] Global mute hotkey (requires macOS permissions)
- [x] Push-to-talk mode with pre-warm and fast chunking
- [x] Notion sync endpoint
- [x] Durable session store (SQLite)
- [x] Installer packaging (`.pkg` + `.dmg`, unsigned)
- [x] Optional WebSocket low-latency stream path

## Next
- Sign + notarize installer for zero Gatekeeper friction
- Overlay UX polish (resize presets, keyboard shortcut customization)
- Guardrails and compliance policy layer
- Notion database mode (write into a DB row, not just page-under-parent)
