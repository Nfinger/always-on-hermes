#!/usr/bin/env bash
set -euo pipefail

LABEL="com.nate.alwaysonhermes"
MENUBAR_LABEL="com.nate.alwaysonhermes.menubar"
OVERLAY_LABEL="com.nate.alwaysonhermes.overlay"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
MENUBAR_PLIST_DST="$HOME/Library/LaunchAgents/${MENUBAR_LABEL}.plist"
OVERLAY_PLIST_DST="$HOME/Library/LaunchAgents/${OVERLAY_LABEL}.plist"
LOG_OUT="/tmp/always-on-hermes.out.log"
LOG_ERR="/tmp/always-on-hermes.err.log"
MENUBAR_LOG_OUT="/tmp/always-on-hermes-menubar.out.log"
MENUBAR_LOG_ERR="/tmp/always-on-hermes-menubar.err.log"
OVERLAY_LOG_OUT="/tmp/always-on-hermes-overlay.out.log"
OVERLAY_LOG_ERR="/tmp/always-on-hermes-overlay.err.log"
BASE_URL="${BASE_URL:-http://127.0.0.1:8899}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  install       Install backend launch agent plist
  start         Start backend service via launchctl
  stop          Stop backend service via launchctl
  restart       Restart backend service
  status        Show backend launchctl + health status
  logs          Tail backend logs
  test          Run backend smoke test
  create-demo   Create a demo general session and print session_id

  ui-open       Open shoulder panel in browser

  menubar-install  Install + load menubar companion launch agent
  menubar-start    Start menubar companion
  menubar-stop     Stop menubar companion
  menubar-status   Show menubar launchctl status
  menubar-logs     Tail menubar logs

  overlay-install  Install + load native overlay launch agent
  overlay-start    Start native overlay
  overlay-stop     Stop native overlay
  overlay-status   Show overlay launchctl status
  overlay-logs     Tail overlay logs
EOF
}

render_backend_plist() {
  cat >"$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${BASE_DIR}/.venv/bin/uvicorn</string>
    <string>app.main:app</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>8899</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${BASE_DIR}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>
</dict>
</plist>
EOF
}

render_menubar_plist() {
  cat >"$MENUBAR_PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${MENUBAR_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${BASE_DIR}/scripts/run_menubar.sh</string>
  </array>

  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${MENUBAR_LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${MENUBAR_LOG_ERR}</string>
</dict>
</plist>
EOF
}

render_overlay_plist() {
  cat >"$OVERLAY_PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${OVERLAY_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${BASE_DIR}/scripts/run_native_overlay.sh</string>
  </array>

  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <false/>

  <key>StandardOutPath</key>
  <string>${OVERLAY_LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${OVERLAY_LOG_ERR}</string>
</dict>
</plist>
EOF
}

install_agent() {
  mkdir -p "$HOME/Library/LaunchAgents"
  render_backend_plist
  launchctl unload "$PLIST_DST" >/dev/null 2>&1 || true
  launchctl load "$PLIST_DST"
  echo "Installed + loaded $LABEL"
}

start_agent() {
  launchctl start "$LABEL" || true
  sleep 1
  curl -fsS "$BASE_URL/health" && echo
}

stop_agent() {
  launchctl stop "$LABEL" || true
}

status_agent() {
  echo "--- launchctl"
  launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | sed -n '1,30p' || echo "not loaded"
  echo "--- health"
  curl -s "$BASE_URL/health" || echo "service not responding"
  echo
}

logs_agent() {
  touch "$LOG_OUT" "$LOG_ERR"
  tail -n 80 -f "$LOG_OUT" "$LOG_ERR"
}

test_agent() {
  bash "$BASE_DIR/scripts/smoke.sh" "$BASE_URL"
}

create_demo() {
  curl -s "$BASE_URL/sessions" \
    -H 'content-type: application/json' \
    -d '{"title":"Always-on Hermes Demo","mode":"general","context_notes":["always on assistant"]}'
  echo
}

ui_open() {
  open "$BASE_URL/panel"
  echo "Shoulder panel opened in browser"
}

menubar_install() {
  mkdir -p "$HOME/Library/LaunchAgents"
  render_menubar_plist
  launchctl unload "$MENUBAR_PLIST_DST" >/dev/null 2>&1 || true
  launchctl load "$MENUBAR_PLIST_DST"
  echo "Installed + loaded $MENUBAR_LABEL"
}

menubar_start() {
  launchctl start "$MENUBAR_LABEL" || true
}

menubar_stop() {
  launchctl stop "$MENUBAR_LABEL" || true
}

menubar_status() {
  launchctl print "gui/$(id -u)/$MENUBAR_LABEL" 2>/dev/null | sed -n '1,30p' || echo "menubar not loaded"
}

menubar_logs() {
  touch "$MENUBAR_LOG_OUT" "$MENUBAR_LOG_ERR"
  tail -n 80 -f "$MENUBAR_LOG_OUT" "$MENUBAR_LOG_ERR"
}

overlay_install() {
  mkdir -p "$HOME/Library/LaunchAgents"
  render_overlay_plist
  launchctl unload "$OVERLAY_PLIST_DST" >/dev/null 2>&1 || true
  launchctl load "$OVERLAY_PLIST_DST"
  echo "Installed + loaded $OVERLAY_LABEL"
}

overlay_start() {
  launchctl start "$OVERLAY_LABEL" || true
}

overlay_stop() {
  launchctl stop "$OVERLAY_LABEL" || true
}

overlay_status() {
  launchctl print "gui/$(id -u)/$OVERLAY_LABEL" 2>/dev/null | sed -n '1,30p' || echo "overlay not loaded"
}

overlay_logs() {
  touch "$OVERLAY_LOG_OUT" "$OVERLAY_LOG_ERR"
  tail -n 80 -f "$OVERLAY_LOG_OUT" "$OVERLAY_LOG_ERR"
}

cmd="${1:-}"
case "$cmd" in
  install) install_agent ;;
  start) start_agent ;;
  stop) stop_agent ;;
  restart) stop_agent; sleep 1; start_agent ;;
  status) status_agent ;;
  logs) logs_agent ;;
  test) test_agent ;;
  create-demo) create_demo ;;
  ui-open) ui_open ;;
  menubar-install) menubar_install ;;
  menubar-start) menubar_start ;;
  menubar-stop) menubar_stop ;;
  menubar-status) menubar_status ;;
  menubar-logs) menubar_logs ;;
  overlay-install) overlay_install ;;
  overlay-start) overlay_start ;;
  overlay-stop) overlay_stop ;;
  overlay-status) overlay_status ;;
  overlay-logs) overlay_logs ;;
  *) usage; exit 1 ;;
esac
