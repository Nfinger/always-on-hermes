#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $(basename "$0") <ssh-host> [remote_dir]"
  echo "Example: $(basename "$0") nate-macbook.local ~/.hermes/tools/interview-copilot"
  exit 1
fi

HOST="$1"
REMOTE_DIR="${2:-~/.hermes/tools/interview-copilot}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

rsync -az --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.pyc' \
  "$BASE_DIR/" "$HOST:$REMOTE_DIR/"

ssh "$HOST" "chmod +x '$REMOTE_DIR/scripts/'*.sh && bash '$REMOTE_DIR/scripts/install_local.sh'"

echo "Remote deploy complete: $HOST:$REMOTE_DIR"
