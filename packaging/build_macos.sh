#!/usr/bin/env bash
# Empaquetado macOS (Fase 8, F8-3, RF-29): .app -> .dmg.
#
# Requiere ejecutarse en macOS con el proyecto instalado (uv pip install -e ".[packaging]")
# — PyInstaller no hace *cross-compiling*: el `.app` solo puede construirse en macOS.
#
# Firma de código y notarización: fuera de alcance de v1 (PRD §8) porque requieren un
# Apple Developer ID de pago. Procedimiento documentado para cuando se disponga de uno
# (no se ejecuta aquí):
#   codesign --deep --force --options runtime \
#       --sign "Developer ID Application: <Nombre> (<TeamID>)" dist/Vigía-eew.app
#   xcrun notarytool submit dist/vigia-eew.dmg --apple-id <correo> --team-id <TeamID> \
#       --password <contraseña-de-app> --wait
#   xcrun stapler staple dist/vigia-eew.dmg
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$RAIZ/dist"
VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('$RAIZ/pyproject.toml','rb'))['project']['version'])")"

echo "== Vigía-eew $VERSION — empaquetado macOS =="

# Same gate CI runs before any packaging job (REQ-OPS-007): the bundle's icon
# is `packaging/icon.icns`, and a missing or malformed one gives an .app with
# the generic application icon and no error anywhere.
python3 "$RAIZ/scripts/check_packaging_assets.py" "$RAIZ"

echo "-- 1/2: .app (PyInstaller) --"
pyinstaller --noconfirm --clean --distpath "$DIST" --workpath "$RAIZ/build" \
    "$RAIZ/packaging/vigia-eew.spec"
APP="$DIST/Vigía-eew.app"
test -d "$APP"

echo "-- 2/2: .dmg --"
# Drag-to-install layout: the .app beside a symlink to /Applications. A .dmg
# with only the bundle in it leaves the user to find Applications themselves,
# and an agent left running from the mounted image disappears on eject.
STAGE="$RAIZ/build/dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="$DIST/vigia-eew-$VERSION.dmg"
rm -f "$DMG"
hdiutil create -volname "Vigía-eew" -srcfolder "$STAGE" -ov -format UDZO "$DMG"

echo "== Listo: $DMG (sin firmar/notarizar — ver cabecera del script) =="
