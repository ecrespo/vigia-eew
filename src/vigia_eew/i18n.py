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
    # The alert's map (ADR-030): the epicentre's caption and the user's own point.
    "coordinates_label": {"en": "Coordinates", "es": "Coordenadas"},
    "your_location": {"en": "Your location", "es": "Tu ubicación"},
    "toast_title": {"en": "Seismic alert {magnitude}", "es": "Alerta sísmica {magnitude}"},
    # The estimate of the shaking (REQ-ALE-011..013). Every branch carries the
    # approximation mark: it is one velocity over a preliminary location.
    "shaking_remaining": {
        "en": "Shaking expected in ≈ {seconds} s",
        "es": "Sacudida estimada en ≈ {seconds} s",
    },
    "shaking_elapsed_seconds": {
        "en": "The shaking should already have arrived ≈ {seconds} s ago",
        "es": "La sacudida ya debió llegar hace ≈ {seconds} s",
    },
    "shaking_elapsed_minutes": {
        "en": "The shaking should already have arrived ≈ {minutes} min ago",
        "es": "La sacudida ya debió llegar hace ≈ {minutes} min",
    },
    "shaking_elapsed_hours": {
        "en": "The shaking should already have arrived ≈ {hours} h ago",
        "es": "La sacudida ya debió llegar hace ≈ {hours} h",
    },
    # A simulated alert says what it is, without reading its detail (REQ-UX-008).
    "drill_label": {
        "en": "DRILL — this is not a real earthquake",
        "es": "SIMULACRO — no es un sismo real",
    },
    "drill_short": {"en": "DRILL", "es": "SIMULACRO"},
    "about_last_drill": {"en": "Last drill", "es": "Último simulacro"},
    "about_drill_never": {"en": "none yet", "es": "ninguno todavía"},
    "about_drill_acknowledged": {
        "en": "{when} · acknowledged",
        "es": "{when} · reconocido",
    },
    "about_drill_unacknowledged": {
        "en": "{when} · not acknowledged",
        "es": "{when} · sin reconocer",
    },
    "tray_ws_connected": {"en": "WS: connected", "es": "WS: conectado"},
    "tray_ws_reconnecting": {"en": "WS: reconnecting…", "es": "WS: reconectando…"},
    "tray_no_alerts_yet": {"en": "No alerts yet", "es": "Sin alertas todavía"},
    # REQ-ALE-003: the user has to be able to see, on their own machine, whether
    # the "above everything" promise actually holds in their session.
    "tray_alert_guaranteed": {
        "en": "Alert: always on top",
        "es": "Alerta: siempre encima",
    },
    "tray_alert_degraded": {
        "en": "Alert: may be covered (Wayland)",
        "es": "Alerta: puede quedar tapada (Wayland)",
    },
    "tray_alert_unknown": {
        "en": "Alert: on top not confirmed here",
        "es": "Alerta: encima no confirmado aquí",
    },
    "tray_pause_notifications": {"en": "Pause notifications", "es": "Pausar notificaciones"},
    "tray_resume_notifications": {"en": "Resume notifications", "es": "Reanudar notificaciones"},
    # Two ways into the same file, deliberately (REQ-GUI-005): the panel for
    # the user this product is written for, the editor for everyone who wants
    # to version the file, copy it between machines, or reach it over SSH.
    "tray_open_panel": {"en": "Configuration…", "es": "Configuración…"},
    "tray_edit_config": {"en": "Edit configuration...", "es": "Editar configuración..."},
    "tray_quit": {"en": "Quit", "es": "Salir"},
    # What the product is, which version is running, and under what terms
    # (T-151). The GPL asks an interactive program to state the licence and
    # the absence of warranty; an agent with no window of its own had nowhere
    # to say either.
    "tray_about": {"en": "About…", "es": "Acerca de…"},
    "about_title": {"en": "About Vigía-eew", "es": "Acerca de Vigía-eew"},
    "about_description": {
        "en": "Real-time desktop earthquake alerts.",
        "es": "Alerta sísmica de escritorio en tiempo real.",
    },
    "about_version": {"en": "Version", "es": "Versión"},
    "about_license": {"en": "License", "es": "Licencia"},
    "about_warranty": {
        "en": "This program comes with absolutely no warranty.",
        "es": "Este programa se distribuye sin ninguna garantía.",
    },
    "about_button": {"en": "About…", "es": "Acerca de…"},
    "about_close": {"en": "Close", "es": "Cerrar"},
    "tray_open_history": {"en": "History…", "es": "Histórico…"},
    # The history view (REQ-HIS-005). Its whole purpose is to answer "why was
    # I not warned about that one?", so the reason has to arrive as a phrase,
    # not as the pipeline's internal word for it.
    # The navigation between screens (REQ-GUI-012): short, they sit on one bar.
    "nav_history": {"en": "History", "es": "Histórico"},
    "nav_settings": {"en": "Settings", "es": "Configuración"},
    "nav_about": {"en": "About", "es": "Acerca de"},
    "history_title": {"en": "Earthquake history", "es": "Histórico de sismos"},
    # CA-113.3: a window opened by `--history` has to say why it is empty.
    "history_unavailable": {
        "en": "The history is not available",
        "es": "El histórico no está disponible",
    },
    "history_column_time": {"en": "Local time", "es": "Hora local"},
    "history_column_magnitude": {"en": "Magnitude", "es": "Magnitud"},
    "history_column_place": {"en": "Place", "es": "Lugar"},
    "history_column_distance": {"en": "Distance", "es": "Distancia"},
    "history_column_source": {"en": "Network", "es": "Red"},
    "history_column_verdict": {"en": "Verdict", "es": "Veredicto"},
    "history_column_reason": {"en": "Reason", "es": "Motivo"},
    "history_verdict_alerted": {"en": "Alerted", "es": "Alertado"},
    "history_verdict_discarded": {"en": "Discarded", "es": "Descartado"},
    "history_verdict_recovered": {"en": "Recovered", "es": "Recuperado"},
    "history_reason_recovered": {
        "en": "Not evaluated: the agent was not watching",
        "es": "No evaluado: el agente no estaba vigilando",
    },
    "history_recover": {"en": "Recover", "es": "Recuperar"},
    "history_recover_days": {"en": "Days back", "es": "Días atrás"},
    "history_recover_hint": {
        "en": "Complete the history from the networks' catalogues. It never alerts.",
        "es": "Completar el histórico desde los catálogos de las redes. Nunca alerta.",
    },
    "history_recover_running": {"en": "Recovering…", "es": "Recuperando…"},
    "history_recover_invalid": {
        "en": "Type a number of days",
        "es": "Escribe un número de días",
    },
    "history_reason_radius": {"en": "Outside the radius", "es": "Fuera del radio"},
    "history_reason_magnitude": {
        "en": "Below the minimum magnitude",
        "es": "Bajo la magnitud mínima",
    },
    "history_reason_country": {"en": "In another country", "es": "En otro país"},
    "history_reason_freshness": {"en": "Not from today", "es": "No es de hoy"},
    "history_reason_duplicate": {
        "en": "Already reported by another network",
        "es": "Ya reportado por otra red",
    },
    "history_filter_magnitude": {"en": "Minimum magnitude", "es": "Magnitud mínima"},
    "history_filter_verdict": {"en": "Verdict", "es": "Veredicto"},
    "history_filter_source": {"en": "Network", "es": "Red"},
    "history_filter_any": {"en": "Any", "es": "Cualquiera"},
    # REQ-HIS-007: the three criteria the store could filter by and the screen could not.
    "history_filter_since": {"en": "From", "es": "Desde"},
    "history_filter_until": {"en": "To", "es": "Hasta"},
    "history_filter_distance": {"en": "Maximum distance (km)", "es": "Distancia máxima (km)"},
    "history_period_invalid": {
        "en": "The period ends before it starts.",
        "es": "El período termina antes de empezar.",
    },
    "history_reading_earthquake": {
        "en": "One line per earthquake",
        "es": "Una línea por sismo",
    },
    "history_arrivals": {
        "en": "Arrivals of this earthquake: {count}",
        "es": "Llegadas de este sismo: {count}",
    },
    "backfill_recovered": {
        "en": "recovered {recovered} · already present {present}",
        "es": "recuperados {recovered} · ya presentes {present}",
    },
    "backfill_skipped": {"en": " · unreadable {skipped}", "es": " · ilegibles {skipped}"},
    "backfill_failed": {"en": "failed: {detail}", "es": "falló: {detail}"},
    "backfill_not_recoverable": {
        "en": "not recoverable: {reason}",
        "es": "no recuperable: {reason}",
    },
    "backfill_no_query_by_date": {
        "en": "the service offers no query by date",
        "es": "el servicio no ofrece consulta por fecha",
    },
    "backfill_refused": {
        "en": "cannot recover {days} days: recovered entries are kept for {limit} "
        "([history] recovered_retention_days)",
        "es": "no se pueden recuperar {days} días: las entradas recuperadas se conservan "
        "{limit} ([history] recovered_retention_days)",
    },
    "backfill_refused_empty": {
        "en": "cannot recover {days} days: the period must be at least one day",
        "es": "no se pueden recuperar {days} días: el periodo debe ser de al menos un día",
    },
    "timelapse_play": {"en": "Play the history", "es": "Reproducir el histórico"},
    "timelapse_pause": {"en": "Pause", "es": "Pausar"},
    "timelapse_stop": {"en": "Stop and show everything", "es": "Detener y mostrar todo"},
    "timelapse_speed": {"en": "Speed", "es": "Velocidad"},
    "timelapse_speed_six_hours": {"en": "6 hours / s", "es": "6 horas / s"},
    "timelapse_speed_day": {"en": "1 day / s", "es": "1 día / s"},
    "timelapse_speed_week": {"en": "1 week / s", "es": "1 semana / s"},
    "timelapse_trail": {"en": "Leave a trail", "es": "Dejar rastro"},
    "timelapse_empty": {"en": "Nothing to play", "es": "Nada que reproducir"},
    "timelapse_truncated": {
        "en": "Playing the {shown} most recent of {total}",
        "es": "Reproduciendo los {shown} más recientes de {total}",
    },
    "history_page_previous": {"en": "Previous page", "es": "Página anterior"},
    "history_page_next": {"en": "Next page", "es": "Página siguiente"},
    "history_filter_clear": {"en": "Clear filters", "es": "Limpiar filtros"},
    # REQ-HIS-008: which stretch of the filtered set is on screen, and of how many.
    "history_stretch": {"en": "{first}–{last} of {total}", "es": "{first}–{last} de {total}"},
    "history_empty": {
        "en": "Nothing recorded yet.",
        "es": "Todavía no hay nada registrado.",
    },
    # The figures of the period (REQ-EST-001..003). Every basis line says how
    # many entries a figure was computed over, and the period they span.
    "history_stats": {"en": "Summary", "es": "Resumen"},
    "history_stats_hint": {
        "en": "The figures of what the filters select",
        "es": "Las cifras de lo que seleccionan los filtros",
    },
    "history_stats_empty": {
        "en": "No data for this filter.",
        "es": "No hay datos para este filtro.",
    },
    "history_stats_per_day": {"en": "Earthquakes per day", "es": "Sismos por día"},
    "history_stats_by_magnitude": {"en": "By magnitude", "es": "Por magnitud"},
    "history_stats_by_verdict": {"en": "By verdict", "es": "Por veredicto"},
    "history_stats_by_reason": {"en": "Discarded, by reason", "es": "Descartados, por motivo"},
    "history_stats_by_source": {"en": "Arrivals by network", "es": "Llegadas por red"},
    "history_stats_latency": {
        "en": "Delivery delay by network (median)",
        "es": "Demora de entrega por red (mediana)",
    },
    "history_stats_over_earthquake": {
        "en": "Earthquakes counted: {count} · {period}",
        "es": "Sismos contados: {count} · {period}",
    },
    "history_stats_over_arrival": {
        "en": "Arrivals counted: {count} · {period}",
        "es": "Llegadas contadas: {count} · {period}",
    },
    "history_stats_over_live": {
        "en": "Live arrivals: {count} · {period}",
        "es": "Llegadas en vivo: {count} · {period}",
    },
    "history_stats_no_figure": {"en": "No figure", "es": "Sin cifra"},
    "history_stats_no_live": {"en": "No live arrivals", "es": "Sin llegadas en vivo"},
    "history_stats_no_reason": {"en": "No reason recorded", "es": "Sin motivo registrado"},
    # The export (REQ-HIS-014): the user's own data, to the user's own disk.
    "history_export": {"en": "Export…", "es": "Exportar…"},
    "history_export_hint": {
        "en": "Save what the filters select to a file on this computer",
        "es": "Guardar en un archivo de este equipo lo que seleccionan los filtros",
    },
    "history_export_format": {"en": "Format", "es": "Formato"},
    "history_export_csv": {"en": "CSV (spreadsheet)", "es": "CSV (hoja de cálculo)"},
    "history_export_geojson": {"en": "GeoJSON (map)", "es": "GeoJSON (mapa)"},
    "history_export_path": {"en": "Save as", "es": "Guardar como"},
    "history_export_browse": {"en": "Choose where…", "es": "Elegir dónde…"},
    "history_export_save": {"en": "Save", "es": "Guardar"},
    "history_export_no_path": {
        "en": "Type where to save the file.",
        "es": "Escribe dónde guardar el archivo.",
    },
    "history_export_no_dialog": {
        "en": "The system's file dialog is not available here. Type the path instead.",
        "es": "El diálogo de archivos del sistema no está disponible aquí. Escribe la ruta.",
    },
    "history_export_done": {
        "en": "Saved {count} entries to {path}",
        "es": "Se guardaron {count} entradas en {path}",
    },
    "history_export_failed": {
        "en": "The file could not be written: {reason}",
        "es": "No se pudo escribir el archivo: {reason}",
    },
    # The map (REQ-MAP-002, REQ-MAP-005).
    # The map draws the filtered set up to a bound, and says so when it stops short.
    "map_truncated": {
        "en": "Showing {shown} of {total}",
        "es": "Mostrando {shown} de {total}",
    },
    "map_unavailable": {
        "en": "Map unavailable (no tiles and no connection). The list still works.",
        "es": "Mapa no disponible (sin teselas ni conexión). El listado sigue funcionando.",
    },
    "map_legend_alerted": {"en": "Alerted", "es": "Alertado"},
    "map_legend_discarded": {"en": "Discarded", "es": "Descartado"},
    "map_legend_recovered": {"en": "Recovered", "es": "Recuperado"},
    "map_legend_size": {"en": "Size = magnitude", "es": "Tamaño = magnitud"},
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
