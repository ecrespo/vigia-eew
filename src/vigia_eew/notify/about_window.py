"""The About screen (T-151, REQ-GUI-010): what this is, which build, whose terms.

A view and nothing else -- every fact it shows is decided in `about.py`,
which needs no display and is tested without one. Opened from the tray's
"About…" entry and from the configuration panel's button, because on a
session where the tray menu never opens the panel is the only way in.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.about import about_info
from vigia_eew.notify.sound import assets_path


def about_view(*, locale_code: str = DEFAULT_LOCALE, on_close: Callable[[], None]) -> Any:
    """Builds the About content: icon, name, then each fact on its own line."""
    info = about_info(locale_code=locale_code)
    lines: list[Any] = []
    icon = assets_path() / "tray_icon.png"
    if icon.is_file():
        # The same file the tray shows. Read through `assets_path` rather than
        # `tray.default_icon_path`: `notify` sits below the tray in the layer
        # contract, and one decorative import is not worth an upward edge.
        lines.append(ft.Image(src=str(icon), width=96, height=96))
    for index, (label, value) in enumerate(info.rows()):
        text = f"{label}: {value}" if label else value
        lines.append(
            ft.Text(
                text,
                size=28 if index == 0 else 15,
                weight=ft.FontWeight.BOLD if index == 0 else None,
                text_align=ft.TextAlign.CENTER,
                selectable=True,
            )
        )
    lines.append(
        ft.FilledButton(
            content=ft.Text(t("about_close", locale_code)), on_click=lambda _e: on_close()
        )
    )
    return ft.SafeArea(
        expand=True,
        content=ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=24,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    ft.Container(
                        width=560,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                            controls=lines,
                        ),
                    )
                ],
            ),
        ),
    )
