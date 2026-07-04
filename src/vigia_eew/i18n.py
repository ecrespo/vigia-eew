"""Internationalization (i18n) of user-facing text (RF-35).

Resolves the effective UI language — an explicit config value, or "auto" to
detect it from the OS locale — and translates the strings shown in the alert
window, the toast, and the tray menu. English and Spanish ship at launch;
any other or undetectable locale falls back to English (never raises).
"""

from __future__ import annotations

import locale
import os

Locale = str

DEFAULT_LOCALE: Locale = "en"
SUPPORTED_LOCALES = {"en", "es"}

_CATALOG: dict[str, dict[Locale, str]] = {
    "seismic_alert_title": {"en": "⚠ SEISMIC ALERT", "es": "⚠ ALERTA SÍSMICA"},
    "acknowledged_button": {"en": "ACKNOWLEDGED", "es": "RECONOCIDO"},
    "depth_label": {"en": "Depth", "es": "Profundidad"},
    "local_time_label": {"en": "Local time (Venezuela)", "es": "Hora local (Venezuela)"},
    "source_label": {"en": "Source", "es": "Fuente"},
    "unknown_location": {"en": "Unknown location", "es": "Ubicación desconocida"},
    "toast_title": {"en": "Seismic alert {magnitude}", "es": "Alerta sísmica {magnitude}"},
    "tray_ws_connected": {"en": "WS: connected", "es": "WS: conectado"},
    "tray_ws_reconnecting": {"en": "WS: reconnecting…", "es": "WS: reconectando…"},
    "tray_no_alerts_yet": {"en": "No alerts yet", "es": "Sin alertas todavía"},
    "tray_pause_notifications": {"en": "Pause notifications", "es": "Pausar notificaciones"},
    "tray_resume_notifications": {"en": "Resume notifications", "es": "Reanudar notificaciones"},
    "tray_edit_config": {"en": "Edit configuration...", "es": "Editar configuración..."},
    "tray_quit": {"en": "Quit", "es": "Salir"},
}


def detect_os_locale() -> Locale:
    """Best-effort OS locale detection; returns a bare language code (RF-35)."""
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env_var)
        if value:
            code = value.split(".")[0].split("_")[0].strip().lower()
            if code:
                return code
    try:
        locale_name: str | None = locale.getlocale()[0]
    except (ValueError, TypeError):
        locale_name = None
    if locale_name:
        return locale_name.split("_")[0].lower()
    return DEFAULT_LOCALE


def resolve_locale(configured: str) -> Locale:
    """Resolves the effective locale from the config value (RF-35).

    `"auto"` detects it from the OS; anything else is used as-is. Falls back
    to English if the resolved value isn't one of `SUPPORTED_LOCALES`.
    """
    code = detect_os_locale() if configured == "auto" else configured
    return code if code in SUPPORTED_LOCALES else DEFAULT_LOCALE


def t(key: str, locale_code: Locale = DEFAULT_LOCALE, **kwargs: object) -> str:
    """Translates `key` into `locale_code`; formats `{placeholders}` if given."""
    entry = _CATALOG.get(key)
    if entry is None:
        return key
    text = entry.get(locale_code, entry[DEFAULT_LOCALE])
    return text.format(**kwargs) if kwargs else text
