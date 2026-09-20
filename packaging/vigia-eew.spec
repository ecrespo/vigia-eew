# -*- mode: python ; coding: utf-8 -*-
"""Especificación PyInstaller — binario nativo onefile (Fase 8, F8-2/F8-3/F8-4, RF-28..RF-30).

Compartida por los tres SO; cada `build_*.{sh,ps1}` invoca
``pyinstaller packaging/vigia-eew.spec`` desde un entorno donde el paquete ya está
instalado (`uv pip install -e .` o el wheel de F8-1) — así los `assets/*.wav` se
resuelven igual que en una instalación normal, sin asumir la disposición del checkout.

Los iconos los genera `packaging/make_icons.py` a partir de una sola marca:
`packaging/icon.ico` (Windows) y `packaging/icon.icns` (macOS, hasta 1024 px para
pantallas Retina). En Linux el icono no va dentro del binario -- va al tema
hicolor, y lo instala `build_linux.sh`.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files

import vigia_eew

block_cipher = None

_PKG_DIR = os.path.dirname(vigia_eew.__file__)
_ASSETS_DIR = os.path.join(_PKG_DIR, "assets")
_VERSION = vigia_eew.__version__

# PyInstaller only embeds an icon on the platform that understands the format:
# `.ico` into the Windows PE resource, `.icns` into the macOS bundle.
_ICO = os.path.join(SPECPATH, "icon.ico")
_ICNS = os.path.join(SPECPATH, "icon.icns")

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
    # `config.toml.example` ships as a package resource so `config.seed_config_if_missing`
    # can seed the user's config on first run (RF-24), the same in the frozen binary as
    # in a wheel/pipx install.
    datas=[
        (_ASSETS_DIR, "vigia_eew/assets"),
        (os.path.join(_PKG_DIR, "config.toml.example"), "vigia_eew"),
        *collect_data_files("desktop_notifier"),
    ],
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
    icon=_ICO if sys.platform == "win32" else None,
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
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Vigía-eew.app",
        icon=_ICNS,
        bundle_identifier="com.ecrespo.vigia-eew",
        version=_VERSION,
        info_plist={
            "NSHighResolutionCapable": True,
            # False on purpose: the agent keeps a Dock icon and a menu-bar item.
            # LSUIElement=True would hide it from the Dock and the app switcher,
            # and on a machine where the tray is the only way in that is one way
            # in fewer (the same failure the Linux desktop entry answers).
            "LSUIElement": False,
            "CFBundleName": "Vigía-eew",
            "CFBundleDisplayName": "Vigía-eew",
            "CFBundleShortVersionString": _VERSION,
            "CFBundleVersion": _VERSION,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHumanReadableCopyright": "© Ernesto Crespo · GPL-3.0-or-later",
        },
    )
