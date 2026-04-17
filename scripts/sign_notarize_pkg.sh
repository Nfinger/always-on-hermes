#!/usr/bin/env bash
set -euo pipefail

# Requires:
# - Developer ID Installer certificate in keychain
# - xcrun notarytool credentials profile configured
#   xcrun notarytool store-credentials "AC_PROFILE" --apple-id ... --team-id ... --password ...

if [ $# -lt 3 ]; then
  echo "Usage: $(basename "$0") <unsigned_pkg> <developer_id_installer_name> <notary_profile>"
  echo "Example: $(basename "$0") dist/always-on-hermes-unsigned.pkg 'Developer ID Installer: Your Name (TEAMID)' AC_PROFILE"
  exit 1
fi

UNSIGNED_PKG="$1"
DEVELOPER_ID="$2"
NOTARY_PROFILE="$3"

if [ ! -f "$UNSIGNED_PKG" ]; then
  echo "Package not found: $UNSIGNED_PKG"
  exit 1
fi

SIGNED_PKG="${UNSIGNED_PKG%.pkg}-signed.pkg"

productsign --sign "$DEVELOPER_ID" "$UNSIGNED_PKG" "$SIGNED_PKG"

echo "Signed package: $SIGNED_PKG"

echo "Submitting for notarization..."
xcrun notarytool submit "$SIGNED_PKG" --keychain-profile "$NOTARY_PROFILE" --wait

echo "Stapling notarization ticket..."
xcrun stapler staple "$SIGNED_PKG"

echo "Done. Notarized package: $SIGNED_PKG"
