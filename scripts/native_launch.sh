#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="$BASE_DIR/native/AlwaysOnHermes/dist-native/Always-on Hermes.app"

if [ ! -d "$APP_PATH" ]; then
  echo "Native app not built yet. Run scripts/native_build.sh first."
  exit 1
fi

open "$APP_PATH"
