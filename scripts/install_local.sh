#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BASE_DIR"

pick_python() {
  for bin in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$bin" >/dev/null 2>&1; then
      echo "$bin"
      return 0
    fi
  done
  return 1
}

PY_BIN="$(pick_python || true)"
if [ -z "${PY_BIN}" ]; then
  echo "No suitable Python interpreter found (need python3.10+)." >&2
  exit 1
fi

# If existing venv is on 3.14+, rebuild with a compatible interpreter.
if [ -x .venv/bin/python ]; then
  VENV_VER="$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  case "$VENV_VER" in
    3.14*|3.15*|3.16*)
      echo "Existing .venv uses Python $VENV_VER (unsupported by current pydantic-core toolchain). Rebuilding..."
      rm -rf .venv
      ;;
  esac
fi

if [ ! -d .venv ]; then
  "$PY_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

# Workaround for PyO3 guard when user only has Python 3.14 locally.
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (review and fill secrets)."
fi

bash "$SCRIPT_DIR/hermes_shoulderctl.sh" install
bash "$SCRIPT_DIR/hermes_shoulderctl.sh" menubar-install
bash "$SCRIPT_DIR/hermes_shoulderctl.sh" overlay-install

bash "$SCRIPT_DIR/hermes_shoulderctl.sh" status
bash "$SCRIPT_DIR/hermes_shoulderctl.sh" menubar-status

AUTO_START_OVERLAY="${AUTO_START_OVERLAY:-1}"
if [ "$AUTO_START_OVERLAY" = "1" ] || [ "$AUTO_START_OVERLAY" = "true" ]; then
  bash "$SCRIPT_DIR/hermes_shoulderctl.sh" overlay-start || true
fi
bash "$SCRIPT_DIR/hermes_shoulderctl.sh" overlay-status || true

echo "Install complete. Native overlay should be visible."
