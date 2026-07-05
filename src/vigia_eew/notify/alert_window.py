"""Undismissable overlay alert window in Tkinter (RF-15..RF-19, ADR-003).

The window is the heart of "impossible to ignore":

  - **Always on top and undecorated** (RF-15): `-topmost` + `overrideredirect`, a
    large centered overlay (or fullscreen depending on config).
  - **Takes focus and re-raises itself** if it loses it (RF-16): `focus_force` +
    `lift`, re-raising on the `<FocusOut>` event.
  - **Does not close by accident** (RF-19): the X (`WM_DELETE_WINDOW`), `Escape`, and
    clicking outside do not close it; only the **ACKNOWLEDGED** button does (an
    explicit close).

The undismissable *policy* (`configure_undismissable`) and `take_focus` are isolated
as functions so they can be tested with a fake root, without a screen. Building the
widget tree uses real Tkinter and is validated with an opt-in smoke test
(`VIGIA_GUI_TESTS=1`).
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Any

from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.presentation import AlertData, severity_color

_MIN_HEIGHT = 620  # visual floor (ADR-003); the real height grows if content requires it


def take_focus(root: Any) -> None:
    """Raises the window and forces focus onto it (RF-16)."""
    root.lift()
    root.focus_force()


def configure_undismissable(root: Any, *, on_close_attempt: Callable[[], None]) -> None:
    """Applies the undismissable window policy (RF-15, RF-16, RF-19)."""
    root.overrideredirect(True)  # no title bar or window buttons
    root.attributes("-topmost", True)  # always above everything else
    root.protocol("WM_DELETE_WINDOW", on_close_attempt)  # the X does not close it
    root.bind("<Escape>", lambda _e: "break")  # Escape does not close it
    root.bind("<FocusOut>", lambda _e: take_focus(root))  # re-raise if it loses focus


class AlertWindow:
    """Alert window for an event; only closes via ACKNOWLEDGED (RF-19)."""

    def __init__(
        self,
        data: AlertData,
        *,
        on_acknowledge: Callable[[], None],
        root: Any = None,
        fullscreen: bool = False,
        locale: str = DEFAULT_LOCALE,
        build: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._data = data
        self._on_acknowledge = on_acknowledge
        self._root: Any = root if root is not None else tk.Tk()
        self._fullscreen = fullscreen
        self._locale = locale
        self._acknowledged = False
        self._log = logger or logging.getLogger("vigia_eew.notify.alert_window")
        if build:
            self._build()

    @property
    def root(self) -> Any:
        return self._root

    def _close_attempt(self) -> None:
        """Attempt to close via X/Escape: deliberately ignored (RF-19)."""
        self._log.info("alert_close_ignored")

    def acknowledge(self) -> None:
        """Acknowledges the alert (the only valid close) and destroys the window (CU-5)."""
        if self._acknowledged:
            return
        self._acknowledged = True
        self._on_acknowledge()
        self._root.destroy()

    def refresh(self, data: AlertData) -> None:
        """Refreshes the displayed data without recreating the window (RF-11)."""
        self._data = data
        if not self._acknowledged:
            self._build()

    # --- UI construction (real Tkinter) ---

    def _build(self) -> None:
        root = self._root
        color = severity_color(self._data.severity)
        root.title(f"Vigía-eew · {t('seismic_alert_title', self._locale)}")
        configure_undismissable(root, on_close_attempt=self._close_attempt)
        if self._fullscreen:
            root.attributes("-fullscreen", True)
            window_width = root.winfo_screenwidth()
        else:
            window_width = 900
        root.configure(bg=color)

        for child in list(root.winfo_children()):
            child.destroy()

        tk.Label(
            root,
            text=t("seismic_alert_title", self._locale),
            font=("Helvetica", 28, "bold"),
            fg="white",
            bg=color,
        ).pack(pady=(28, 6))
        tk.Label(
            root, text=self._data.magnitude, font=("Helvetica", 110, "bold"), fg="white", bg=color
        ).pack(pady=4)

        details = (
            f"{self._data.place}\n"
            f"{self._data.distance}\n"
            f"{t('depth_label', self._locale)}: {self._data.depth}\n"
            f"{t('local_time_label', self._locale)}: {self._data.local_time}\n"
            f"{t('source_label', self._locale)}: {self._data.source}"
        )
        # `wraplength` is mandatory here: without it, a line wider than the window
        # (e.g. "Local time (Venezuela): ...") gets clipped against the edge instead
        # of wrapping, because the window has a fixed size and is not resizable
        # (overrideredirect, RF-15).
        tk.Label(
            root,
            text=details,
            font=("Helvetica", 22),
            fg="white",
            bg=color,
            justify="center",
            wraplength=window_width - 80,
        ).pack(pady=18)

        tk.Button(
            root,
            text=t("acknowledged_button", self._locale),
            font=("Helvetica", 24, "bold"),
            fg=color,
            bg="white",
            activeforeground=color,
            padx=40,
            pady=16,
            command=self.acknowledge,
        ).pack(pady=(20, 30))

        if not self._fullscreen:
            # Dynamic height: computing it from the already-packed content avoids an
            # extra line (e.g. a long `place` that wraps due to `wraplength`) getting
            # clipped against a fixed height — the window is neither resizable nor
            # scrollable (overrideredirect, RF-15), so the height must always
            # accommodate all the actual content.
            root.update_idletasks()
            window_height = max(_MIN_HEIGHT, root.winfo_reqheight())
            self._center(window_width, window_height)

        take_focus(root)

    def _center(self, width: int, height: int) -> None:
        root = self._root
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")
