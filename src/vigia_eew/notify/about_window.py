"""The About window (T-151, REQ-GUI-010): what this is, which build, whose terms.

A window and nothing else -- every fact it shows is decided in `about.py`,
which needs no display and is tested without one. Opened from the tray's
"About…" entry and from the configuration panel's button, because on a
session where the tray menu never opens the panel is the only way in.
"""

from __future__ import annotations

from typing import Any

from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.about import about_info
from vigia_eew.notify.sound import assets_path

#: Points added to the product name, over the window's own font.
_TITLE_BUMP = 8


def open_about(root: Any, *, locale_code: str = DEFAULT_LOCALE) -> Any:
    """Builds the About window over `root`. Tk thread only, like every window."""
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk

    info = about_info(locale_code=locale_code)
    window = tk.Toplevel(root)
    window.title(t("about_title", locale_code))
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)

    _place_icon(frame, window)
    base = tkfont.nametofont("TkDefaultFont", root=window)
    title_font = base.copy()
    title_font.configure(size=abs(int(base.cget("size"))) + _TITLE_BUMP, weight="bold")

    for index, (label, value) in enumerate(info.rows()):
        text = f"{label}: {value}" if label else value
        ttk.Label(
            frame,
            text=text,
            font=title_font if index == 0 else base,
            justify="center",
            anchor="center",
        ).pack(fill="x", pady=(0, 10 if index == 0 else 2))

    ttk.Button(frame, text=t("about_close", locale_code), command=window.destroy).pack(pady=(16, 0))
    return window


def _place_icon(frame: Any, window: Any) -> None:
    """The product's own mark, if Tk can read it. Never fatal: it is decoration."""
    import tkinter as tk
    from tkinter import ttk

    try:
        # The same file the tray shows. Read through `assets_path` rather than
        # `tray.default_icon_path`: `notify` sits below the tray in the layer
        # contract, and one decorative import is not worth an upward edge.
        photo = tk.PhotoImage(master=window, file=str(assets_path() / "tray_icon.png"))
    except Exception:  # noqa: BLE001 - a missing or unreadable icon costs nothing here
        return
    label = ttk.Label(frame, image=photo)
    # Tk keeps no reference of its own; without this the image is collected and
    # the label draws empty.
    label.image = photo  # type: ignore[attr-defined]
    label.pack(pady=(0, 12))
