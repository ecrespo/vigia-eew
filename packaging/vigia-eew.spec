# -*- mode: python ; coding: utf-8 -*-
"""Especificación PyInstaller — binario nativo onefile (Fase 8, F8-2/F8-3/F8-4, RF-28..RF-30).

Compartida por los tres SO; cada `build_*.{sh,ps1}` invoca
``pyinstaller packaging/vigia-eew.spec`` desde un entorno donde el paquete ya está
instalado (`uv pip install -e .` o el wheel de F8-1) — así los `assets/*.wav` se
resuelven igual que en una instalación normal, sin asumir la disposición del checkout.

No se define un icono (`icon=...`): no hay ningún asset gráfico en el repo todavía.
Para agregar uno, colocar `packaging/icon.ico` (Windows) / `packaging/icon.icns`
(macOS) y referenciarlo aquí.
"""

import os

from PyInstaller.utils.hooks import collect_data_files

import vigia_eew

block_cipher = None

_ASSETS_DIR = os.path.join(os.path.dirname(vigia_eew.__file__), "assets")

# `desktop_notifier.common` carga su ícono default con
# `importlib.resources.files("desktop_notifier.resources")` — una referencia dinámica
# por nombre de módulo que el análisis estático de PyInstaller no detecta. Sin esto,
# el subpaquete `desktop_notifier/resources/` (con `python.png`) queda fuera del
# bundle y el binario falla en runtime con
# `ModuleNotFoundError: No module named 'desktop_notifier.resources'` (visto en el
# `.deb` de la release v0.1.2). `collect_data_files` copia sus archivos de datos;
# el hiddenimport asegura que el subpaquete en sí (su `__init__.py`) se incluya.
a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[],
    binaries=[],
    datas=[(_ASSETS_DIR, "vigia_eew/assets"), *collect_data_files("desktop_notifier")],
    # `desktop-notifier` resuelve su backend (dbus-fast en Linux, UserNotifications en
    # macOS, WinRT en Windows) con imports condicionales que PyInstaller a veces no
    # detecta solo con el análisis estático; si el binario falla en runtime con
    # `ModuleNotFoundError`, reconstruir con `pyinstaller --debug=imports` para ver
    # qué falta y sumarlo aquí.
    hiddenimports=["desktop_notifier", "desktop_notifier.resources"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="vigia-eew",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # ventana de alerta Tkinter; no necesita consola (F8-2)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS: además del binario onefile de arriba, produce el `.app` que `build_macos.sh`
# empaqueta en un `.dmg` (F8-3). En Linux/Windows este bloque no se ejecuta.
import sys  # noqa: E402 (después de las variables de PyInstaller, por claridad)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Vigía-eew.app",
        icon=None,
        bundle_identifier="com.ecrespo.vigia-eew",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
        },
    )
