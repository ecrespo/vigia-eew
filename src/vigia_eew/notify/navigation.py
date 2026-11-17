"""The way from one screen to another (REQ-GUI-012, ADR-031).

The history, the configuration panel and About each used to be reachable only
from the tray menu -- and on GNOME/Wayland that menu may not open. `--settings`
and `--history` are doors into one screen each; this bar is what makes one
door enough, by leading from any screen to the other two.

The bar is composed **into each screen's view**, not into the shell
([[notification#Navigation is part of the screen]]). The shell renders either
the alert or the screen, so a bar that lives inside the screen is absent
whenever an alert has the window -- with no condition anybody could forget.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft

from vigia_eew.i18n import DEFAULT_LOCALE, t

__all__ = ["DESTINATIONS", "Entry", "bar_of", "entries", "framed", "screen_of"]

#: The screens, by the key `FletShell.show_screen` knows them by, with the
#: label and the icon each gets. The order is the order on the bar.
DESTINATIONS: tuple[tuple[str, str, ft.IconData], ...] = (
    ("history", "nav_history", ft.Icons.HISTORY),
    ("panel", "nav_settings", ft.Icons.SETTINGS),
    ("about", "nav_about", ft.Icons.INFO_OUTLINE),
)

#: What marks the bar inside a framed view, so it can be found again.
_BAR_KEY = "navigation"


@dataclass(frozen=True, slots=True)
class Entry:
    """One destination, as the bar shows it."""

    key: str
    label: str
    icon: ft.IconData
    current: bool


def entries(current: str, *, locale_code: str = DEFAULT_LOCALE) -> list[Entry]:
    """Works out the bar without touching a control."""
    return [
        Entry(key=key, label=t(label, locale_code), icon=icon, current=key == current)
        for key, label, icon in DESTINATIONS
    ]


def framed(
    view: Any,
    current: str,
    on_select: Callable[[str], None],
    *,
    locale_code: str = DEFAULT_LOCALE,
) -> Any:
    """`view` with the navigation above it: what a screen hands to the shell.

    The destination the user is on is disabled rather than only tinted: it
    differs in what it does, so the bar reads the same in a screenshot and to
    somebody who cannot tell the two colours apart.
    """

    def button(entry: Entry) -> Any:
        return ft.TextButton(
            content=ft.Text(entry.label, weight=ft.FontWeight.BOLD if entry.current else None),
            icon=entry.icon,
            data=entry.key,
            disabled=entry.current,
            on_click=lambda _event, key=entry.key: on_select(key),
        )

    bar = ft.Container(
        key=_BAR_KEY,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Row(
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            controls=[button(entry) for entry in entries(current, locale_code=locale_code)],
        ),
    )
    return ft.Column(expand=True, spacing=0, controls=[bar, view])


def bar_of(view: Any) -> Any:
    """The navigation inside a framed view, or None if it has none."""
    controls = getattr(view, "controls", None) or []
    first = controls[0] if controls else None
    return first if getattr(first, "key", None) == _BAR_KEY else None


def screen_of(view: Any) -> Any:
    """The screen a framed view wraps; the view itself if it is not framed."""
    return view.controls[-1] if bar_of(view) is not None else view
