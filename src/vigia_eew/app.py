"""Agent orchestration (RF-26, RF-21; concurrency ADR-006).

`Application` runs the agent. It does not build it -- that is `wiring.py`
(ADR-023), and the split is what stopped this module from being the one seam
every feature had to pass through (architecture evaluation P1-1).

What is left here is the part that is genuinely about running:

  - the ADR-006 concurrency model: **Flet's UI loop on the main thread** (ADR-030),
    the **asyncio loop on a worker thread**, events crossing via `AsyncioUiBridge`;
  - `execute()`, the full agent; `run_tui()`, the headless dashboard (RF-36);
    `simulate()`, one event, no network (RF-21); `open_settings()`, the panel alone;
  - the callbacks that need a *running* application -- pause, exit, after-acknowledge;
  - shutdown, which has to work whichever order the threads got started in
    (ADR-002).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vigia_eew.agent_state import AgentRuntime, AgentState, Stoppable
from vigia_eew.config import ReferencePoint, Settings, default_config_path
from vigia_eew.models import SeismicEvent
from vigia_eew.notify.controller import AlertController
from vigia_eew.notify.queue import AsyncioUiBridge
from vigia_eew.simulation import simulated_event
from vigia_eew.state import StateStore
from vigia_eew.wiring import UiRunner, Wiring, run_flet

#: How long shutdown waits for the worker to publish its runtime. The worker
#: normally gets there in milliseconds; this is the budget for the case where
#: the quit lands inside the publication window, not for a worker that hung.
#: The `join` that follows has its own, longer one.
_RUNTIME_READY_S = 2.0


class Application:
    """Runs the Vigía agent (full, TUI, or `--simulate`)."""

    def __init__(
        self,
        cfg: Settings,
        *,
        state: StateStore | None = None,
        logger: logging.Logger | None = None,
        manual_reference: bool = True,
        detect_location: Callable[[], ReferencePoint | None] | None = None,
        config_path: Path | str | None = None,
        run_ui: UiRunner | None = None,
    ) -> None:
        self.cfg = cfg
        self.state = state or StateStore()
        self._log = logger or logging.getLogger("vigia_eew.app")
        self._agent_state = AgentState()
        self.wiring = Wiring(
            cfg,
            self.state,
            self._agent_state,
            logger=self._log,
            detect_location=detect_location,
        )
        self._runtime = AgentRuntime()
        self._shell: Any = None
        self._run_ui = run_ui or run_flet
        self._worker: threading.Thread | None = None
        self._ctrl: AlertController | None = None
        self._exit_on_drain = False
        self._manual_reference = manual_reference
        self._config_path = config_path
        self._tray_icon: Any = None
        self._tui_app: Any = None

    # --- Callbacks that need a running application ---

    def _on_ui_thread(self, action: Callable[[], Any]) -> None:
        """Runs `action` on the UI thread, or not at all if there is no window.

        Every tray callback goes through here. The tray runs on its own thread
        and Flet's controls belong to the UI loop (ADR-006), so touching a
        control from the callback directly works right up until it does not.
        """
        if self._shell is not None:
            self._shell.after(0, action)

    def _toggle_pause(self) -> None:
        """Tray callback: pause/resume (RF-34)."""
        self._on_ui_thread(lambda: self._ctrl.toggle_pause() if self._ctrl is not None else None)

    def _exit_from_tray(self) -> None:
        """Tray callback: exits the agent (RF-34)."""
        self._on_ui_thread(lambda: self._shell.quit())

    def _edit_config(self) -> None:
        """Tray callback: opens `config.toml` in the OS's associated app (RF-34)."""
        self.wiring.open_config(self._config_file)

    # Tray callbacks that open a screen: panel, About, history -- UI thread only.

    def _open_panel(self) -> None:
        self._on_ui_thread(lambda: self.wiring.open_panel(self._shell, self._config_file))

    def _open_about(self) -> None:
        self._on_ui_thread(lambda: self.wiring.open_about(self._shell))

    def _open_history(self) -> None:
        self._on_ui_thread(lambda: self.wiring.open_history(self._shell))

    @property
    def _config_file(self) -> Path:
        """The file both ways into the configuration act on."""
        return Path(self._config_path) if self._config_path is not None else default_config_path()

    def _after_acknowledge(self, _ev: SeismicEvent) -> None:
        """Closes the app once the queue has drained, where that applies (simulate)."""
        if (
            self._exit_on_drain
            and self._ctrl is not None
            and self._ctrl.alert_queue.current is None
            and self._ctrl.alert_queue.pending == 0
            and self._shell is not None
        ):
            self._shell.after(150, self._shell.quit)

    # --- Startup glue ---

    def _prepare(self, *, resolve_location: bool = False) -> None:
        self.wiring.configure(resolve_location=resolve_location and not self._manual_reference)

    def _gui_controller(self, shell: Any, *, loop_mode: bool) -> AlertController:
        ctrl = self.wiring.build_gui_controller(
            shell,
            on_acknowledge=self._after_acknowledge,
            worker_loop=(lambda: self._runtime.loop) if loop_mode else (lambda: None),
        )
        self._ctrl = ctrl
        return ctrl

    def _build_tray(self) -> Any:
        return self.wiring.build_tray(
            paused=lambda: self._ctrl.paused if self._ctrl is not None else False,
            toggle_pause=self._toggle_pause,
            edit_config=self._edit_config,
            exit_agent=self._exit_from_tray,
            open_panel=self._open_panel,
            open_history=self._open_history,
            open_about=self._open_about,
        )

    def _wire_tui(self, tui_app: Any) -> AlertController:
        """Wires controller, pipeline and supervisor for the TUI (RF-36).

        No asyncio<->UI bridge here: Textual runs on the same loop as the
        supervisor, so the processor calls `ctrl.enqueue` directly.
        """
        ctrl = self.wiring.build_tui_controller(tui_app, on_acknowledge=self._after_acknowledge)
        self._ctrl = ctrl
        raw_queue: asyncio.Queue[Any] = asyncio.Queue()
        processor = self.wiring.build_processor(
            raw_queue, on_alert=ctrl.enqueue, on_update=ctrl.enqueue
        )
        tui_app.bind_supervisor(self.wiring.build_supervisor(raw_queue, processor))
        return ctrl

    # --- Run modes ---

    def simulate(self) -> None:
        """Injects the simulated event and shows the alert until acknowledged (RF-21)."""
        self._prepare()
        self._exit_on_drain = True

        def show(shell: Any) -> None:
            ctrl = self._gui_controller(shell, loop_mode=False)
            ctrl.enqueue(simulated_event(self.cfg.reference, self.cfg.severity))
            self._log.info("simulation_started")

        self._in_window(standalone=True, then=show)

    def open_settings(self) -> None:
        """Opens the configuration panel alone, with no agent behind it (REQ-GUI-009)."""
        # @lat: [[configuration#A door into the panel that is not the tray]]
        # Standalone: closing the panel -- the only screen -- ends the run.
        self._in_window(
            standalone=True, then=lambda shell: self.wiring.open_panel(shell, self._config_file)
        )

    def _in_window(self, *, standalone: bool, then: Callable[[Any], Any]) -> None:
        """Runs Flet until its window is gone; `then(shell)` fills it, on the UI loop."""

        async def main(page: Any) -> None:  # on Flet's loop: the shell must be built here
            self._shell = self.wiring.build_shell(page, standalone=standalone)
            then(self._shell)

        self._run_ui(main)

    def run_tui(self, *, simulate: bool = False) -> None:
        """Starts the agent with the headless TUI dashboard (RF-36, ADR-013).

        With `simulate=True` (`--simulate --tui`) it injects the simulated
        event into the running TUI without starting real ingestion.
        """
        from vigia_eew.tui import VigiaTuiApp

        self._prepare(resolve_location=not simulate)
        if simulate:
            self._tui_app = VigiaTuiApp(
                state=self._agent_state,
                locale_code=self.wiring.locale,
                on_start=self._inject_simulated_alert,
            )
            self._ctrl = self.wiring.build_tui_controller(
                self._tui_app, on_acknowledge=self._after_acknowledge
            )
        else:
            self._tui_app = VigiaTuiApp(state=self._agent_state, locale_code=self.wiring.locale)
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
        try:
            self._in_window(standalone=False, then=self._start_agent)
        except KeyboardInterrupt:
            self._log.info("keyboard_interrupt")
        finally:
            self._stop(self._worker)

    def _start_agent(self, shell: Any) -> None:
        """Controller, tray, bridge and worker thread, once the window exists."""
        ctrl = self._gui_controller(shell, loop_mode=True)
        self._tray_icon = self._build_tray()
        if self._tray_icon is not None:
            self._tray_icon.start()
        bridge = AsyncioUiBridge(sink=ctrl.enqueue)
        bridge.start_polling(shell, interval_ms=100)
        thread = threading.Thread(target=self._run_loop, args=(bridge,), daemon=True)
        thread.start()
        self._worker = thread
        self._log.info("agent_started")

    def _run_loop(self, bridge: AsyncioUiBridge) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        raw_queue: asyncio.Queue[Any] = asyncio.Queue()
        processor = self.wiring.build_processor(
            raw_queue, on_alert=bridge.publish, on_update=bridge.publish
        )
        sup = self.wiring.build_supervisor(raw_queue, processor)
        # Both at once: the gap between publishing the loop and publishing the
        # supervisor was the race itself (ADR-002).
        self.publish_runtime(loop, sup)
        try:
            loop.run_until_complete(sup.run())
        except Exception as exc:  # noqa: BLE001 - log any loop failure
            self._log.warning("loop_error type=%s detail=%s", type(exc).__name__, exc)
        finally:
            loop.close()

    # --- Shutdown ---

    def publish_runtime(self, loop: asyncio.AbstractEventLoop, sup: Stoppable) -> None:
        """Hands the worker's loop and supervisor to the threads that read them."""
        self._runtime.publish(loop, sup)

    def _stop(
        self, thread: threading.Thread | None, *, runtime_timeout: float = _RUNTIME_READY_S
    ) -> None:
        """Coordinated shutdown: the tray icon, the supervisor, and the worker thread."""
        if self._tray_icon is not None:
            self._tray_icon.stop()
        self.wiring.close_history()
        if thread is None:  # the window never came up, so no worker was started
            return
        runtime = self._runtime.await_ready(runtime_timeout)
        if runtime is None:
            # The worker never published: it died before assembling the
            # pipeline, or the quit beat it to the first statement. Nothing to
            # cancel, and saying so beats a silent five-second join.
            self._log.warning("stop_before_runtime_ready timeout=%.1fs", runtime_timeout)
        else:
            loop, sup = runtime
            loop.call_soon_threadsafe(sup.request_stop)
        thread.join(timeout=5.0)
        if self._shell is not None:
            self._shell.quit()  # idempotent, and safe on a window already gone
