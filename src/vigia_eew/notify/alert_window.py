"""Undismissable alert, drawn in Flet with a map of the epicentre (RF-15..RF-19, ADR-003).

The alert is the heart of "impossible to ignore":

  - **Always on top and undecorated** (RF-15): `always_on_top` + a hidden
    title bar, a large centered window (or fullscreen depending on config).
  - **Takes focus and re-raises itself** if it loses it (RF-16): the shell
    brings the window to the front on every `blur`.
  - **Does not close by accident** (RF-19): the X is intercepted
    (`prevent_close`) and Escape does nothing; only **ACKNOWLEDGED** -- the
    button or ENTER -- closes it.

Next to the text there is a **map**: a pin on the epicentre whose caption
carries the place, the coordinates and the magnitude, a circle sized by the
magnitude, and the user's reference point, so "162 km from Caracas" has a
picture to go with it. Without tiles (offline) the map is blank but the pin,
the caption and the coordinates in the text are still there.

The undismissable *policy* (`configure_undismissable`) and `take_focus` are
isolated as functions over a window object so they can be tested with a fake,
without a screen. The controls themselves are plain Flet dataclasses and can
be built and inspected without a display too.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import flet as ft

from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify import ui_scale
from vigia_eew.notify.map_view import build_alert_map
from vigia_eew.notify.presentation import AlertData, severity_color

#: Text colour over each severity's background. White on amber does not read.
_ON_SEVERITY = {"info": "#FFFFFF", "warning": "#1B2028", "critical": "#FFFFFF"}

#: Height of the map when it sits beside the text or under it.
MAP_HEIGHT = 560


def take_focus(window: Any, call_async: Callable[[Callable[[], Any]], None]) -> None:
    """Raises the window and brings it to the front (RF-16)."""
    window.visible = True
    window.focused = True
    call_async(window.to_front)


# @lat: [[notification#Non-dismissable alert contract]]
def configure_undismissable(window: Any, *, fullscreen: bool = False) -> None:
    """Applies the undismissable window policy (RF-15, RF-16, RF-19).

    Every way out of this window in one place: no title bar and no
    minimise, the X is intercepted (the shell ignores it while an alert is
    up), and the window stays above everything else. Escape has no binding
    at all -- and ENTER acknowledges, which the shell routes to the alert.
    """
    window.always_on_top = True  # always above everything else
    window.title_bar_hidden = True  # no title bar or window buttons
    window.title_bar_buttons_hidden = True
    window.prevent_close = True  # the X does not close it
    window.minimizable = False
    window.skip_task_bar = False
    window.resizable = False
    if fullscreen:
        window.full_screen = True
    else:
        window.full_screen = False
        window.width, window.height = ui_scale.ALERT_SIZE


class AlertWindow:
    """Alert for one event; only closes via ACKNOWLEDGED (RF-19)."""

    def __init__(
        self,
        data: AlertData,
        *,
        on_acknowledge: Callable[[], None],
        host: Any = None,
        fullscreen: bool = False,
        locale: str = DEFAULT_LOCALE,
        build: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._data = data
        self._on_acknowledge = on_acknowledge
        self._shell = host  # the FletShell that draws it
        self._fullscreen = fullscreen
        self._locale = locale
        self._acknowledged = False
        self._log = logger or logging.getLogger("vigia_eew.notify.alert_window")
        self.view = ft.Container(expand=True, padding=24)
        if build:
            self._build()
            if host is not None:
                host.show_alert(
                    self.view,
                    configure=lambda window: configure_undismissable(
                        window, fullscreen=self._fullscreen
                    ),
                    on_enter=self.acknowledge,
                    bgcolor=severity_color(data.severity),
                )

    @property
    def data(self) -> AlertData:
        return self._data

    @property
    def acknowledged(self) -> bool:
        return self._acknowledged

    def acknowledge(self) -> None:
        """Acknowledges the alert (the only valid close) and gives the window back (CU-5)."""
        if self._acknowledged:
            return
        self._acknowledged = True
        self._on_acknowledge()
        if self._shell is not None:
            self._shell.clear_alert(self.view)

    def refresh(self, data: AlertData) -> None:
        """Refreshes the displayed data without recreating the window (RF-11)."""
        self._data = data
        if self._acknowledged:
            return
        self._build()
        if self._shell is not None:
            self._shell.page.bgcolor = severity_color(data.severity)
            self._shell.update()

    # --- Controls ---

    def _build(self) -> None:
        data = self._data
        color = severity_color(data.severity)
        ink = _ON_SEVERITY.get(data.severity, "#FFFFFF")
        self.view.bgcolor = color
        self.view.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.CENTER,  # fullscreen: centred, not top-heavy
            controls=[
                ft.ResponsiveRow(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=24,
                    run_spacing=24,
                    controls=[
                        self._text_column(data, ink, color),
                        ft.Container(
                            col=ui_scale.ALERT_MAP_COLUMNS,
                            height=MAP_HEIGHT,
                            border_radius=16,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            border=ft.Border.all(3, ink),
                            content=build_alert_map(data, locale_code=self._locale),
                        ),
                    ],
                )
            ],
        )

    def _text_column(self, data: AlertData, ink: str, color: str) -> Any:
        loc = self._locale

        def line(label: str, value: str) -> Any:
            return ft.Text(
                spans=[
                    ft.TextSpan(f"{label}: ", ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    ft.TextSpan(value),
                ],
                size=20,
                color=ink,
                selectable=True,
            )

        return ft.Column(
            col=ui_scale.ALERT_TEXT_COLUMNS,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Text(
                    t("seismic_alert_title", loc),
                    size=30,
                    weight=ft.FontWeight.BOLD,
                    color=ink,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    data.magnitude,
                    size=96,
                    weight=ft.FontWeight.BOLD,
                    color=ink,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    data.place,
                    size=24,
                    weight=ft.FontWeight.W_600,
                    color=ink,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(data.distance, size=20, color=ink, text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                line(t("coordinates_label", loc), data.coordinates),
                line(t("depth_label", loc), data.depth),
                line(t("local_time_label", loc), data.local_time),
                line(t("source_label", loc), data.source),
                ft.Container(height=16),
                ft.FilledButton(
                    content=ft.Text(
                        t("acknowledged_button", loc), size=24, weight=ft.FontWeight.BOLD
                    ),
                    autofocus=True,
                    style=ft.ButtonStyle(
                        bgcolor=ink,
                        color=color,
                        padding=ft.Padding.symmetric(horizontal=40, vertical=20),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=lambda _e: self.acknowledge(),
                ),
            ],
        )
