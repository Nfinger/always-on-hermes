#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
PROJECT_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"
APP_NAME="Always-on Hermes"
BUNDLE_ID="com.nate.alwaysonhermes.native"
OUT_DIR="$ROOT_DIR/dist-native"
APP_DIR="$OUT_DIR/${APP_NAME}.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RES_DIR="$APP_DIR/Contents/Resources"
PAYLOAD_DIR="$RES_DIR/payload"
BIN_NAME="AlwaysOnHermes"

cd "$ROOT_DIR"

swift build -c release

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR" "$PAYLOAD_DIR"

cp -f ".build/release/$BIN_NAME" "$MACOS_DIR/$BIN_NAME"
chmod +x "$MACOS_DIR/$BIN_NAME"

# Bundle backend payload so target Macs do not need manual pip/setup.
rsync -a --delete "$PROJECT_ROOT/app/" "$PAYLOAD_DIR/app/"
rsync -a --delete "$PROJECT_ROOT/scripts/" "$PAYLOAD_DIR/scripts/"
rsync -a --delete "$PROJECT_ROOT/.venv/" "$PAYLOAD_DIR/.venv/"
cp -f "$PROJECT_ROOT/requirements.txt" "$PAYLOAD_DIR/requirements.txt"
cp -f "$PROJECT_ROOT/.env.example" "$PAYLOAD_DIR/.env.example"
mkdir -p "$PAYLOAD_DIR/data"

cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleVersion</key>
  <string>0.1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleExecutable</key>
  <string>${BIN_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

mkdir -p "$OUT_DIR/dmg-src"
rm -rf "$OUT_DIR/dmg-src/${APP_NAME}.app"
cp -R "$APP_DIR" "$OUT_DIR/dmg-src/${APP_NAME}.app"

cat > "$OUT_DIR/dmg-src/README.txt" <<TXT
Always-on Hermes (Native macOS app)

Install:
1) Drag '${APP_NAME}.app' into Applications
2) Launch from Applications

Expected:
- Menu bar icon appears
- Native floating overlay appears
- App attempts to start backend services automatically
TXT

hdiutil create -volname "Always-on-Hermes-Native" -srcfolder "$OUT_DIR/dmg-src" -ov -format UDZO "$OUT_DIR/${APP_NAME}-native-unsigned.dmg" >/dev/null

echo "Built app: $APP_DIR"
echo "Built dmg: $OUT_DIR/${APP_NAME}-native-unsigned.dmg"
