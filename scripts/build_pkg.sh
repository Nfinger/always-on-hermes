#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$BASE_DIR/dist"
PKG_ROOT="$OUT_DIR/pkgroot"
PKG_SCRIPTS_DIR="$OUT_DIR/pkgscripts"
PAYLOAD_DIR="$PKG_ROOT/usr/local/share/always-on-hermes/interview-copilot"
IDENTIFIER="com.nate.alwaysonhermes"
VERSION="0.6.0"

mkdir -p "$OUT_DIR"
rm -rf "$PKG_ROOT" "$PKG_SCRIPTS_DIR"
mkdir -p "$PAYLOAD_DIR" "$PKG_SCRIPTS_DIR"

rsync -az --delete \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.pyc' \
  --exclude '.git' \
  --exclude 'dist' \
  "$BASE_DIR/" "$PAYLOAD_DIR/"

cat >"$PKG_SCRIPTS_DIR/postinstall" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/private/var/tmp/always-on-hermes-postinstall.log"
exec >>"$LOG_FILE" 2>&1

echo "[$(date)] postinstall start"
PAYLOAD_SRC="/usr/local/share/always-on-hermes/interview-copilot"

if [ ! -d "$PAYLOAD_SRC" ]; then
  echo "Payload not found at $PAYLOAD_SRC"
  exit 1
fi

CONSOLE_USER="$(stat -f%Su /dev/console || true)"
echo "Console user: ${CONSOLE_USER:-<none>}"
if [ -z "$CONSOLE_USER" ] || [ "$CONSOLE_USER" = "root" ] || [ "$CONSOLE_USER" = "loginwindow" ]; then
  echo "No active non-root console user detected."
  exit 0
fi

TARGET_HOME="$(dscl . -read "/Users/$CONSOLE_USER" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
if [ -z "$TARGET_HOME" ]; then
  TARGET_HOME="/Users/$CONSOLE_USER"
fi

TARGET_DIR="$TARGET_HOME/.hermes/tools/interview-copilot"
mkdir -p "$(dirname "$TARGET_DIR")"
/usr/bin/rsync -a --delete "$PAYLOAD_SRC/" "$TARGET_DIR/"
/usr/sbin/chown -R "$CONSOLE_USER":staff "$TARGET_DIR"
echo "Synced payload to $TARGET_DIR"

# Add a global wrapper command for convenience.
mkdir -p /usr/local/bin
cat >/usr/local/bin/hermes_shoulderctl <<'WRAP'
#!/usr/bin/env bash
exec "$HOME/.hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh" "$@"
WRAP
chmod +x /usr/local/bin/hermes_shoulderctl

# Zero-touch provisioning when bundled venv exists.
if [ -x "$TARGET_DIR/.venv/bin/python" ]; then
  UID_NUM="$(id -u "$CONSOLE_USER")"
  echo "Bundled venv found. Running zero-touch launch setup as user $CONSOLE_USER (uid $UID_NUM)."
  /bin/launchctl asuser "$UID_NUM" sudo -u "$CONSOLE_USER" bash "$TARGET_DIR/scripts/hermes_shoulderctl.sh" install || true
  /bin/launchctl asuser "$UID_NUM" sudo -u "$CONSOLE_USER" bash "$TARGET_DIR/scripts/hermes_shoulderctl.sh" menubar-install || true
  /bin/launchctl asuser "$UID_NUM" sudo -u "$CONSOLE_USER" bash "$TARGET_DIR/scripts/hermes_shoulderctl.sh" overlay-install || true
  /bin/launchctl asuser "$UID_NUM" sudo -u "$CONSOLE_USER" bash "$TARGET_DIR/scripts/hermes_shoulderctl.sh" overlay-start || true
else
  echo "Bundled venv not found at $TARGET_DIR/.venv/bin/python"
fi

# Copy postinstall log into user's Library for easy access.
mkdir -p "$TARGET_HOME/Library/Logs"
cp -f "$LOG_FILE" "$TARGET_HOME/Library/Logs/always-on-hermes-postinstall.log" || true
chown "$CONSOLE_USER":staff "$TARGET_HOME/Library/Logs/always-on-hermes-postinstall.log" 2>/dev/null || true

echo "[$(date)] postinstall done"
exit 0
EOF
chmod +x "$PKG_SCRIPTS_DIR/postinstall"

pkgbuild \
  --root "$PKG_ROOT" \
  --scripts "$PKG_SCRIPTS_DIR" \
  --identifier "$IDENTIFIER" \
  --version "$VERSION" \
  "$OUT_DIR/always-on-hermes-unsigned.pkg"

echo "Built package: $OUT_DIR/always-on-hermes-unsigned.pkg"
echo "Payload path inside pkg: $PAYLOAD_DIR"
echo "Postinstall copies payload to active user's ~/.hermes/tools/interview-copilot"
echo "This package now includes .venv and attempts zero-touch start (backend + menubar + overlay)."
echo "Postinstall logs (if needed): /private/var/tmp/always-on-hermes-postinstall.log and ~/Library/Logs/always-on-hermes-postinstall.log"
