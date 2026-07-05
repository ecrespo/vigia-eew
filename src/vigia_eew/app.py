"""Application assembly (RF-26, RF-21; concurrency ADR-006).

`Application` wires all layers into a runnable agent:

  ingestion (WS + REST) -> asyncio queue -> processor (normalize/filter/dedup)
  -> asyncio<->Tk bridge -> alert controller (window + sound + toast).

Follows the ADR-006 concurrency model: **Tkinter on the main thread** and the
**asyncio loop on a worker thread**; events cross via `AsyncioTkBridge`.

  - `execute()`: full agent (real ingestion + notification).
  - `simulate()`: injects the simulated event into the notification layer, no network (RF-21).

The parts with logic (supervisor task selection, controller construction) are
isolated into testable methods; thread/GUI startup is integration glue.
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
from vigia_eew.config import ReferencePoint, Settings, default_config_path
from vigia_eew.i18n import resolve_locale
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.rest_funvisis import FUNVISISPoller
from vigia_eew.ingest.rest_usgs import RESTReconciler
from vigia_eew.ingest.ws_emsc import WSIngestor
from vigia_eew.logging_conf import configure_logging
from vigia_eew.models import SeismicEvent, SeverityLevel
from vigia_eew.notify.controller import AlertController
from vigia_eew.notify.presentation import AlertData
from vigia_eew.notify.queue import AsyncioTkBridge
from vigia_eew.notify.sound import SoundPlayer
from vigia_eew.notify.toast import Toaster
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filter import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.processor import Processor
from vigia_eew.simulation import simulated_event
from vigia_eew.state import StateStore
from vigia_eew.supervisor import Supervisor

_WindowFactory = Callable[[AlertData, SeverityLevel, Callable[[], None]], Any]


class Application:
    """Builds and runs the Vigía agent (full mode or `--simulate`)."""

    def __init__(
        self,
        cfg: Settings,
        *,
        state: StateStore | None = None,
        logger: logging.Logger | None = None,
        manual_reference: bool = True,
        detect_location: Callable[[], ReferencePoint | None] | None = None,
        config_path: Path | str | None = None,
    ) -> None:
        self.cfg = cfg
        self.state = state or StateStore()
        self._log = logger or logging.getLogger("vigia_eew.app")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sup: Supervisor | None = None
        self._root: Any = None
        self._ctrl: AlertController | None = None
        self._exit_on_drain = False
        self._manual_reference = manual_reference
        self._detect_location = detect_location or geoloc.detect_ip_location
        self._config_path = config_path
        self._agent_state = AgentState()
        self._tray_icon: tray.TrayIcon | None = None
        self._tui_app: Any = None
        self._locale = resolve_locale(cfg.notification.language)

    # --- Testable wiring ---

    def _build_supervisor(
        self, raw_queue: asyncio.Queue[RawMessage], processor: Any
    ) -> Supervisor:
        """Registers the agent's tasks based on the enabled sources (RNF-04)."""
        sup = Supervisor(handle_signals=False)  # signals are handled by the main thread
        if self.cfg.sources_emsc.enabled:
            sup.add(
                "ws",
                lambda: WSIngestor(
                    self.cfg.sources_emsc, raw_queue, state=self._agent_state
                ).run(),
            )
        if self.cfg.sources_usgs.enabled:
            sup.add(
                "rest",
                lambda: RESTReconciler(
                    self.cfg.sources_usgs,
                    self.cfg.reference,
                    self.cfg.filter,
                    self.state,
                    raw_queue,
                ).run(),
            )
        if self.cfg.sources_funvisis.enabled:
            sup.add(
                "funvisis",
                lambda: FUNVISISPoller(self.cfg.sources_funvisis, raw_queue).run(),
            )
        sup.add("pipeline", lambda: processor.run())
        return sup

    def _resolve_user_country(self) -> str | None:
        """ISO-A2 code of the user's country: config override, or derived by
        reverse-geocoding the (already resolved) reference point (RF-37)."""
        configured = self.cfg.filter.country
        if configured != "auto":
            return configured.upper()
        return geocode.country_of(self.cfg.reference.lat, self.cfg.reference.lon)

    def _build_geo_filter(self) -> GeoFilter:
        """Builds the geo/magnitude filter, wiring the country filter when enabled (RF-37).

        Fail-safe: if the filter is enabled but the user's country can't be determined,
        the filter stays inert (never suppresses alerts on a detection gap).
        """
        if not self.cfg.filter.country_filter:
            return GeoFilter(self.cfg.filter)
        user_country = self._resolve_user_country()
        if user_country is None:
            self._log.warning("country_filter_no_country_using_none")
            return GeoFilter(self.cfg.filter)
        self._log.info("country_filter_active country=%s", user_country)
        return GeoFilter(
            self.cfg.filter, user_country=user_country, country_of=geocode.country_of
        )

    def _build_controller(
        self,
        create_window: _WindowFactory,
        *,
        play_sound: Callable[[SeverityLevel], None] | None = None,
        publish_toast: Callable[[SeismicEvent], None] | None = None,
    ) -> AlertController:
        """Creates the alert controller with the injected effects."""
        ctrl = AlertController(
            create_window=create_window,
            play_sound=play_sound,
            send_toast=publish_toast,
            on_acknowledge=self._after_acknowledge,
            reference_name=self.cfg.reference.name,
            state=self._agent_state,
            locale_code=self._locale,
        )
        self._ctrl = ctrl
        return ctrl

    def _build_tray(self) -> tray.TrayIcon | None:
        """Builds the tray icon if enabled (RF-34); best-effort."""
        if not self.cfg.notification.tray_icon:
            return None
        try:
            icon = tray.build_icon(
                state=self._agent_state,
                paused=lambda: self._ctrl.paused if self._ctrl is not None else False,
                toggle_pause=self._toggle_pause,
                edit_config=self._edit_config,
                exit=self._exit_from_tray,
                locale_code=self._locale,
            )
            return tray.TrayIcon(icon)
        except Exception as exc:  # noqa: BLE001 - deliberate best-effort (RF-34)
            self._log.warning("tray_unavailable type=%s detail=%s", type(exc).__name__, exc)
            return None

    def _toggle_pause(self) -> None:
        """Tray icon callback: pause/resume (RF-34).

        Scheduled via `root.after(0, ...)` because `resume()` can trigger the
        creation of a Tk window, and Tkinter is not thread-safe (ADR-006) — the
        tray icon runs on its own thread, not on the Tk thread.
        """
        if self._root is None or self._ctrl is None:
            return

        def do_toggle() -> None:
            if self._ctrl is None:
                return
            if self._ctrl.paused:
                self._ctrl.resume()
            else:
                self._ctrl.pause()

        self._root.after(0, do_toggle)

    def _exit_from_tray(self) -> None:
        """Tray icon callback: exits the agent (RF-34)."""
        if self._root is not None:
            self._root.after(0, self._root.quit)

    def _edit_config(self) -> None:
        """Tray icon callback: opens `config.toml` with the OS's associated app (RF-34)."""
        path = (
            Path(self._config_path)
            if self._config_path is not None
            else default_config_path()
        )
        tray.open_config(path)

    def _after_acknowledge(self, _ev: SeismicEvent) -> None:
        """After acknowledge: closes the app if the queue is now empty
        and applicable (simulate).
        """
        if (
            self._exit_on_drain
            and self._ctrl is not None
            and self._ctrl.alert_queue.current is None
            and self._ctrl.alert_queue.pending == 0
            and self._root is not None
        ):
            self._root.after(150, self._root.quit)

    # --- Real GUI construction ---

    def _prepare(self, *, resolve_location: bool = False) -> None:
        configure_logging(self.cfg.logging)
        self.state.load()
        if resolve_location and not self._manual_reference:
            self._resolve_automatic_reference()

    def _resolve_automatic_reference(self) -> None:
        """Resolves the reference point by IP when there's no manual `[reference]` (RF-33)."""
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

    def _new_root(self) -> Any:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()  # hidden root; each alert is a Toplevel
        self._root = root
        return root

    def _controller_for_gui(self, root: Any, *, loop_mode: bool) -> AlertController:
        import tkinter as tk

        from vigia_eew.notify.alert_window import AlertWindow

        sound = SoundPlayer(enabled=self.cfg.notification.sound)
        toaster = Toaster(reference_name=self.cfg.reference.name, locale_code=self._locale)

        def create_window(
            data: AlertData, severity: SeverityLevel, on_acknowledge: Callable[[], None]
        ) -> AlertWindow:
            return AlertWindow(
                data,
                on_acknowledge=on_acknowledge,
                root=tk.Toplevel(root),
                fullscreen=self.cfg.notification.fullscreen,
                locale=self._locale,
            )

        def play_sound(severity: SeverityLevel) -> None:
            threading.Thread(target=sound.play, args=(severity,), daemon=True).start()

        def publish_toast(ev: SeismicEvent) -> None:
            if loop_mode and self._loop is not None:
                asyncio.run_coroutine_threadsafe(toaster.notify(ev), self._loop)
            else:
                threading.Thread(
                    target=lambda: asyncio.run(toaster.notify(ev)), daemon=True
                ).start()

        play_sound_fn = play_sound if self.cfg.notification.sound else None
        return self._build_controller(
            create_window, play_sound=play_sound_fn, publish_toast=publish_toast
        )

    # --- Headless TUI dashboard construction (RF-36, ADR-013) ---

    def _controller_for_tui(self, tui_app: Any) -> AlertController:
        """Builds the alert controller wired to the TUI (RF-36).

        There is no toast in this mode (there's no desktop session on a
        headless server); sound stays best-effort like in the Tk path.
        """
        sound = SoundPlayer(enabled=self.cfg.notification.sound)

        def create_window(
            data: AlertData, severity: SeverityLevel, on_acknowledge: Callable[[], None]
        ) -> Any:
            return tui_app.push_alert(data, severity, on_acknowledge)

        def play_sound(severity: SeverityLevel) -> None:
            threading.Thread(target=sound.play, args=(severity,), daemon=True).start()

        play_sound_fn = play_sound if self.cfg.notification.sound else None
        ctrl = self._build_controller(
            create_window, play_sound=play_sound_fn, publish_toast=None
        )
        tui_app.bind_controller(ctrl)
        return ctrl

    def _wire_tui(self, tui_app: Any) -> AlertController:
        """Wires the controller + supervisor for the TUI dashboard (RF-36).

        Unlike `execute()`, no asyncio<->Tk bridge is needed: Textual runs on
        the same asyncio loop as the supervisor worker, so the processor calls
        `ctrl.enqueue` directly.
        """
        ctrl = self._controller_for_tui(tui_app)
        raw_queue: asyncio.Queue[RawMessage] = asyncio.Queue()
        processor = Processor(
            raw_queue,
            Normalizer(self.cfg.reference, self.cfg.severity),
            self._build_geo_filter(),
            Deduplicator(self.cfg.dedup, self.state),
            on_alert=ctrl.enqueue,
            on_update=ctrl.enqueue,
        )
        sup = self._build_supervisor(raw_queue, processor)
        self._sup = sup
        tui_app.bind_supervisor(sup)
        return ctrl

    # --- Run modes ---

    def simulate(self) -> None:
        """Injects the simulated event and shows the alert until acknowledged (RF-21)."""
        self._prepare()
        self._exit_on_drain = True
        root = self._new_root()
        ctrl = self._controller_for_gui(root, loop_mode=False)
        ctrl.enqueue(simulated_event(self.cfg.reference, self.cfg.severity))
        self._log.info("simulation_started")
        root.mainloop()

    def run_tui(self, *, simulate: bool = False) -> None:
        """Starts the agent with the headless TUI dashboard (RF-36, ADR-013).

        With `simulate=True` (`--simulate --tui`), injects the simulated event
        into the running TUI without starting the real ingestion, analogous to
        `simulate()` for the Tk path.
        """
        from vigia_eew.tui import VigiaTuiApp

        self._prepare(resolve_location=not simulate)
        if simulate:
            self._tui_app = VigiaTuiApp(
                state=self._agent_state,
                locale_code=self._locale,
                on_start=self._inject_simulated_alert,
            )
            self._controller_for_tui(self._tui_app)
        else:
            self._tui_app = VigiaTuiApp(state=self._agent_state, locale_code=self._locale)
            self._wire_tui(self._tui_app)
        self._log.info("tui_simulation_started" if simulate else "tui_started")
        self._tui_app.run()

    def _inject_simulated_alert(self) -> None:
        """Enqueues the simulated event into the running TUI (`--simulate --tui`)."""
        if self._ctrl is not None:
            self._ctrl.enqueue(simulated_event(self.cfg.reference, self.cfg.severity))

    def execute(self) -> None:
        """Starts the full agent: ingestion + pipeline + notification (CU-1, CU-2)."""
        self._prepare(resolve_location=True)
        root = self._new_root()
        ctrl = self._controller_for_gui(root, loop_mode=True)
        self._tray_icon = self._build_tray()
        if self._tray_icon is not None:
            self._tray_icon.start()
        bridge = AsyncioTkBridge(sink=ctrl.enqueue)
        bridge.start_polling(root, interval_ms=100)
        thread = threading.Thread(target=self._run_loop, args=(bridge,), daemon=True)
        thread.start()
        self._log.info("agent_started")
        try:
            root.mainloop()
        except KeyboardInterrupt:
            self._log.info("keyboard_interrupt")
        finally:
            self._stop(thread)

    def _run_loop(self, bridge: AsyncioTkBridge) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        raw_queue: asyncio.Queue[RawMessage] = asyncio.Queue()
        processor = Processor(
            raw_queue,
            Normalizer(self.cfg.reference, self.cfg.severity),
            self._build_geo_filter(),
            Deduplicator(self.cfg.dedup, self.state),
            on_alert=bridge.publish,
            on_update=bridge.publish,
        )
        sup = self._build_supervisor(raw_queue, processor)
        self._sup = sup
        try:
            loop.run_until_complete(sup.run())
        except Exception as exc:  # noqa: BLE001 - log any loop failure
            self._log.warning("loop_error type=%s detail=%s", type(exc).__name__, exc)
        finally:
            loop.close()

    def _stop(self, thread: threading.Thread) -> None:
        """Coordinated shutdown: stops the tray icon, the supervisor, and the asyncio thread."""
        if self._tray_icon is not None:
            self._tray_icon.stop()
        if self._loop is not None and self._sup is not None:
            self._loop.call_soon_threadsafe(self._sup.request_stop)
        thread.join(timeout=5.0)
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:  # noqa: BLE001 - root may already be destroyed
                pass
