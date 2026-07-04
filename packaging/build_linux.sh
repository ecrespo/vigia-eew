#!/usr/bin/env bash
# Empaquetado Linux (Fase 8, F8-4, RF-30): binario onefile + AppImage + .deb/.rpm.
#
# Requiere, ya instalados en el PATH (F8-5 los instala en el runner de CI; en local hay
# que instalarlos a mano, este script no instala nada por sí mismo):
#   - `pyinstaller` (pip install -e ".[packaging]" o del venv de desarrollo)
#   - `linuxdeploy` + `appimagetool` (AppImage) — https://github.com/linuxdeploy/linuxdeploy
#     y https://github.com/AppImage/appimagetool
#   - `fpm` (.deb/.rpm) — `gem install --no-document fpm` (necesita Ruby)
#   - `rpmbuild` en el PATH si se construye el `.rpm` (paquete `rpm` de la distro)
#
# Empaquetado snap: fuera de alcance de v1 (solo se documenta como evolución futura;
# no hay `snapcraft.yaml` en este repo todavía).
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$RAIZ/dist"
VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('$RAIZ/pyproject.toml','rb'))['project']['version'])")"

echo "== Vigía-eew $VERSION — empaquetado Linux =="

echo "-- 1/3: binario onefile (PyInstaller) --"
pyinstaller --noconfirm --clean --distpath "$DIST" --workpath "$RAIZ/build" \
    "$RAIZ/packaging/vigia-eew.spec"
BIN="$DIST/vigia-eew"
test -x "$BIN"

echo "-- 2/3: AppImage --"
if command -v linuxdeploy >/dev/null && command -v appimagetool >/dev/null; then
    APPDIR="$RAIZ/build/AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    cp "$BIN" "$APPDIR/usr/bin/vigia-eew"
    cat > "$APPDIR/vigia-eew.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Vigía-eew
Comment=Alerta sísmica de escritorio en tiempo real
Exec=vigia-eew
Icon=vigia-eew
Categories=Utility;
Terminal=false
EOF
    # Icono placeholder (PNG 1x1 transparente válido): falta un asset gráfico real
    # (ver nota en vigia-eew.spec). Un archivo vacío hace fallar a linuxdeploy/CImg
    # al intentar decodificarlo como imagen.
    base64 -d > "$APPDIR/vigia-eew.png" <<< \
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    linuxdeploy --appdir "$APPDIR" --desktop-file "$APPDIR/vigia-eew.desktop" \
        --icon-file "$APPDIR/vigia-eew.png" --output appimage
    mv ./*.AppImage "$DIST/vigia-eew-$VERSION-x86_64.AppImage"
else
    echo "   (omitido: falta linuxdeploy/appimagetool en el PATH)" >&2
fi

echo "-- 3/3: .deb y .rpm (fpm) --"
if command -v fpm >/dev/null; then
    fpm -s dir -t deb -n vigia-eew -v "$VERSION" \
        --description "Agente de escritorio de alerta sísmica en tiempo real" \
        --url "https://github.com/ecrespo/vigia-eew" \
        --license "GPL-3.0-or-later" \
        --package "$DIST/vigia-eew_${VERSION}_amd64.deb" \
        "$BIN=/usr/bin/vigia-eew"
    if command -v rpmbuild >/dev/null; then
        fpm -s dir -t rpm -n vigia-eew -v "$VERSION" \
            --description "Agente de escritorio de alerta sísmica en tiempo real" \
            --url "https://github.com/ecrespo/vigia-eew" \
            --package "$DIST/vigia-eew-${VERSION}.x86_64.rpm" \
            "$BIN=/usr/bin/vigia-eew"
    else
        echo "   (omitido .rpm: falta rpmbuild en el PATH)" >&2
    fi
else
    echo "   (omitido: falta fpm en el PATH — gem install --no-document fpm)" >&2
fi

echo "== Listo. Artefactos en $DIST =="
ls -la "$DIST"
