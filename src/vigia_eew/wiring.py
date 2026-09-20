"""Dependency construction for the agent (REQ-ING-009, ADR-023).

`app.py` used to be the composition root and a god-module at once: it imported
22 of the project's modules while the next highest fan-out in the tree was 5,
and every feature since v0.1.0 had to pass through it. That is architecture
evaluation P1-1, and the problem was never its size -- it was that assembling
the dependencies and running the agent were the same file, so neither could be
read or changed without the other.

Everything that *builds* something lives here. `Application` keeps what it is
actually for: starting the threads, crossing events between them, and stopping
cleanly. The callbacks that need the running application -- pausing, exiting,
what happens after an acknowledgement -- are passed in rather than reached for.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vigia_eew import geocode, geoloc, tray
from vigia_eew.agent_state import AgentState
from vigia_eew.config import ReferencePoint, Settings
from vigia_eew.history import HistoryStore, HistoryWriter
from vigia_eew.i18n import resolve_locale, t
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.registry import (
    SOURCE_REGISTRY,
    IngestContext,
    priority_rank,
    validate_registry,
)
from vigia_eew.logging_conf import configure_logging
from vigia_eew.models import SeismicEvent, SeverityLevel
from vigia_eew.notify.controller import AlertController
from vigia_eew.notify.presentation import AlertData
from vigia_eew.notify.sound import SoundPlayer
from vigia_eew.notify.toast import Toaster
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.processor import Processor
from vigia_eew.state import StateStore
from vigia_eew.supervisor import Supervisor

WindowFactory = Callable[[AlertData, SeverityLevel, Callable[[], None]], Any]
#: Reads the worker's loop, or None if it has not published one yet.
LoopSource = Callable[[], asyncio.AbstractEventLoop | None]


class Wiring:
    """Builds the agent's parts from its configuration."""

    def __init__(
        self,
        cfg: Settings,
        state: StateStore,
        agent_state: AgentState,
        *,
        logger: logging.Logger | None = None,
        detect_location: Callable[[], ReferencePoint | None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.state = state
        self.agent_state = agent_state
        self.locale = resolve_locale(cfg.notification.language)
        self._log = logger or logging.getLogger("vigia_eew.wiring")
        self._detect_location = detect_location or geoloc.detect_ip_location
        self._panel_window: Any = None
        self._history_window: Any = None
        self._history: HistoryWriter | None = None

    # --- Startup ---

    def configure(self, *, resolve_location: bool) -> None:
        """Sets up logging and loads persisted state, resolving the reference if asked."""
        configure_logging(self.cfg.logging)
        # First line in the log, on purpose: when somebody reports "it did not
        # come up over my game", this is the entry that answers it (REQ-ALE-003).
        env = self.agent_state.presentation
        self._log.info(
            "presentation_guarantee session=%s guarantee=%s reason=%s",
            env.session,
            env.guarantee,
            env.reason,
        )
        self.state.load()
        if resolve_location:
            self.resolve_automatic_reference()

    # @lat: [[state#Reference point resolution happens once, in the application layer]]
    def resolve_automatic_reference(self) -> None:
        """Resolves the reference point by IP when there is no manual one (RF-33)."""
        cached = self.state.cached_location()
        if cached is not None:
            self.cfg.reference = cached
            self._log.info("ip_location_cache name=%s", cached.name)
            return
        detected = self._detect_location()
        if detected is None:
            self._log.warning("ip_location_fallback_default")
            return
        self.cfg.reference = detected
        self.state.cache_location(detected)
        self.state.save()
        self._log.info("ip_location_detected name=%s", detected.name)

    # --- Pipeline ---

    def resolve_user_country(self) -> str | None:
        """ISO-A2 code of the user's country: config override, or reverse-geocoded (RF-37)."""
        configured = self.cfg.filter.country
        if configured != "auto":
            return configured.upper()
        return geocode.country_of(self.cfg.reference.lat, self.cfg.reference.lon)

    def build_geo_filter(self) -> GeoFilter:
        """Builds the geo/magnitude filter, wiring the country filter when enabled (RF-37).

        Fail-safe: if the filter is enabled but the country cannot be determined,
        it stays inert. A detection gap must never suppress an alert.
        """
        timezone = self.cfg.notification.timezone
        if not self.cfg.filter.country_filter:
            return GeoFilter(self.cfg.filter, timezone=timezone)
        user_country = self.resolve_user_country()
        if user_country is None:
            self._log.warning("country_filter_no_country_using_none")
            return GeoFilter(self.cfg.filter, timezone=timezone)
        self._log.info("country_filter_active country=%s", user_country)
        return GeoFilter(
            self.cfg.filter,
            user_country=user_country,
            country_of=geocode.country_of,
            timezone=timezone,
        )

    def build_processor(
        self,
        raw_queue: asyncio.Queue[RawMessage],
        *,
        on_alert: Callable[[SeismicEvent], None],
        on_update: Callable[[SeismicEvent], None],
    ) -> Processor:
        """Assembles normalize -> filter -> dedup.

        Both run modes used to build this separately and identically, which is
        how a filter added to one and forgotten in the other stays invisible
        until somebody is not warned.
        """
        return Processor(
            raw_queue,
            Normalizer(self.cfg.reference, self.cfg.severity),
            self.build_geo_filter(),
            # The rank is resolved here, where the registry is already known,
            # and handed over as a plain mapping. The pipeline needs the order
            # the user declared, not the catalogue it was declared in.
            Deduplicator(self.cfg.dedup, self.state, priority_rank=priority_rank(self.cfg)),
            on_alert=on_alert,
            on_update=on_update,
            record=self._history_sink(),
        )

    def build_history(self) -> HistoryWriter | None:
        """Opens the history, or gives it up and says so (REQ-HIS-002).

        Best-effort by construction, like the tray and the toast: a read-only
        directory, a file from a newer version, a disk that is full -- none of
        them may cost an alert, so all of them end here as a warning and a
        `None`. Art. 1 and Art. 3.
        """
        if not self.cfg.history.enabled:
            self._log.info("history_disabled")
            return None
        if self._history is not None:
            return self._history
        try:
            store = HistoryStore(retention_days=self.cfg.history.retention_days).open()
        except Exception as exc:  # noqa: BLE001 - deliberate best-effort (REQ-HIS-002)
            self._log.warning("history_unavailable type=%s detail=%s", type(exc).__name__, exc)
            return None
        self._history = HistoryWriter(store)
        self._log.info(
            "history_open path=%s retention_days=%d",
            store.path,
            self.cfg.history.retention_days,
        )
        return self._history

    def _history_sink(self) -> Callable[[Any], None] | None:
        writer = self.build_history()
        return None if writer is None else writer.submit

    def close_history(self) -> None:
        """Closes the file on shutdown, best-effort."""
        if self._history is not None:
            self._history.close()
            self._history = None

    def build_supervisor(
        self, raw_queue: asyncio.Queue[RawMessage], processor: Processor
    ) -> Supervisor:
        """Registers one supervised task per enabled source, plus the pipeline (RNF-04).

        Adding a network does not come back here: it is one entry in the
        source registry (REQ-ING-009).
        """
        validate_registry()
        ctx = IngestContext(
            cfg=self.cfg,
            state=self.state,
            queue=raw_queue,
            agent_state=self.agent_state,
        )
        sup = Supervisor(handle_signals=False)  # signals are handled by the main thread
        for spec in SOURCE_REGISTRY:
            if spec.is_enabled(self.cfg):
                sup.add(spec.task_name, spec.make_task(ctx))
        sup.add("pipeline", lambda: processor.run())
        # Supervised like any other task, and for the same reason: its failure
        # must isolate. A history that dies takes nothing with it.
        #
        # Asked for here rather than assumed to exist: `build_history` is
        # idempotent, so the supervisor does not silently depend on the
        # processor having been built first.
        writer = self.build_history()
        if writer is not None:
            sup.add("history", writer.run)
        return sup

    # --- Notification ---

    def build_controller(
        self,
        create_window: WindowFactory,
        *,
        on_acknowledge: Callable[[SeismicEvent], None],
        play_sound: Callable[[SeverityLevel], None] | None = None,
        publish_toast: Callable[[SeismicEvent], None] | None = None,
    ) -> AlertController:
        """Creates the alert controller with its three effects injected."""
        return AlertController(
            create_window=create_window,
            play_sound=play_sound,
            send_toast=publish_toast,
            on_acknowledge=on_acknowledge,
            reference_name=self.cfg.reference.name,
            state=self.agent_state,
            locale_code=self.locale,
        )

    def _sound_effect(self) -> Callable[[SeverityLevel], None] | None:
        """Sound on its own thread, or nothing when disabled."""
        if not self.cfg.notification.sound:
            return None
        sound = SoundPlayer(enabled=True)

        def play(severity: SeverityLevel) -> None:
            threading.Thread(target=sound.play, args=(severity,), daemon=True).start()

        return play

    def build_gui_controller(
        self,
        root: Any,
        *,
        on_acknowledge: Callable[[SeismicEvent], None],
        worker_loop: LoopSource,
    ) -> AlertController:
        """The Tk path: a real window, sound, and a desktop toast."""
        import tkinter as tk

        from vigia_eew.notify.alert_window import AlertWindow

        toaster = Toaster(reference_name=self.cfg.reference.name, locale_code=self.locale)

        def create_window(
            data: AlertData, severity: SeverityLevel, acknowledge: Callable[[], None]
        ) -> AlertWindow:
            return AlertWindow(
                data,
                on_acknowledge=acknowledge,
                root=tk.Toplevel(root),
                fullscreen=self.cfg.notification.fullscreen,
                locale=self.locale,
            )

        def publish_toast(ev: SeismicEvent) -> None:
            loop = worker_loop()
            if loop is not None:
                asyncio.run_coroutine_threadsafe(toaster.notify(ev), loop)
            else:
                threading.Thread(
                    target=lambda: asyncio.run(toaster.notify(ev)), daemon=True
                ).start()

        return self.build_controller(
            create_window,
            on_acknowledge=on_acknowledge,
            play_sound=self._sound_effect(),
            publish_toast=publish_toast,
        )

    def build_tui_controller(
        self, tui_app: Any, *, on_acknowledge: Callable[[SeismicEvent], None]
    ) -> AlertController:
        """The TUI path (RF-36): no toast -- a headless server has no desktop session."""

        def create_window(
            data: AlertData, severity: SeverityLevel, acknowledge: Callable[[], None]
        ) -> Any:
            return tui_app.push_alert(data, severity, acknowledge)

        ctrl = self.build_controller(
            create_window,
            on_acknowledge=on_acknowledge,
            play_sound=self._sound_effect(),
            publish_toast=None,
        )
        tui_app.bind_controller(ctrl)
        return ctrl

    # --- Tray ---

    def build_tray(
        self,
        *,
        paused: Callable[[], bool],
        toggle_pause: Callable[[], None],
        edit_config: Callable[[], None],
        exit_agent: Callable[[], None],
        open_panel: Callable[[], None] | None = None,
        open_history: Callable[[], None] | None = None,
    ) -> tray.TrayIcon | None:
        """Builds the tray icon if enabled (RF-34); best-effort, never fatal."""
        if not self.cfg.notification.tray_icon:
            return None
        try:
            icon = tray.build_icon(
                state=self.agent_state,
                paused=paused,
                toggle_pause=toggle_pause,
                edit_config=edit_config,
                exit=exit_agent,
                open_panel=open_panel,
                open_history=open_history,
                locale_code=self.locale,
            )
            return tray.TrayIcon(icon)
        except Exception as exc:  # noqa: BLE001 - deliberate best-effort (RF-34)
            self._log.warning("tray_unavailable type=%s detail=%s", type(exc).__name__, exc)
            return None

    def open_config(self, path: Path) -> None:
        """Opens `config.toml` with the OS's associated application (RF-34)."""
        tray.open_config(path)

    def open_history(self, root: Any) -> Any:
        """Opens the history window (REQ-HIS-005). Tk thread only, like the panel.

        Reads the history through its **own** store rather than the writer's
        connection: the view runs on the Tk thread and the writer on a worker
        one, and a reader that blocks behind a write would put the interface at
        the mercy of a disk. Two connections to one SQLite file is what the
        engine is for.

        A history that cannot be opened for reading leaves the entry doing
        nothing and says so, which is the same best-effort rule the writer
        follows -- nothing about the history may cost an alert.
        """
        import tkinter as tk

        from vigia_eew.notify.history_window import HistoryWindow

        if self._history_window is not None and self._history_window.winfo_exists():
            self._history_window.lift()
            return self._history_window
        try:
            store = HistoryStore(prune_on_open=False).open()
        except Exception as exc:  # noqa: BLE001 - deliberate best-effort (REQ-HIS-002)
            self._log.warning("history_view_unavailable type=%s detail=%s", type(exc).__name__, exc)
            return None
        window = tk.Toplevel(root)
        window.title(t("history_title", self.locale))
        HistoryWindow(
            window,
            store,
            locale_code=self.locale,
            zone=self.cfg.notification.timezone,
            reference=(self.cfg.reference.lat, self.cfg.reference.lon),
        )
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_history(store, window))
        self._history_window = window
        return window

    def _close_history(self, store: HistoryStore, window: Any) -> None:
        store.close()
        self._history_window = None
        window.destroy()

    def open_panel(self, root: Any, path: Path) -> Any:
        """Opens the configuration panel in its own window (REQ-GUI-005).

        Must be called on the Tk thread -- `Application` schedules it, because
        the tray that asks for it runs on its own (ADR-006).

        A second call raises the window that is already open instead of
        building another. Two panels over one file would be the external-edit
        conflict of CA-108.7 with itself.
        """
        import tkinter as tk

        from vigia_eew.config_writer import ConfigWriter
        from vigia_eew.notify.config_panel import ConfigPanel, PanelModel

        if self._panel_window is not None and self._panel_window.winfo_exists():
            self._panel_window.lift()
            return self._panel_window
        window = tk.Toplevel(root)
        window.title("Vigía-eew")
        ConfigPanel(window, PanelModel(ConfigWriter(path)))
        self._panel_window = window
        return window
