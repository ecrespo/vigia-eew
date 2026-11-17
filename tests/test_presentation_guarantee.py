"""Tests for the declared scope of the alert guarantee (REQ-ALE-003, HU-106).

The product promises an alert that cannot be ignored. On Wayland it cannot
keep that promise through any toolkit, and the way it fails is the problem:
the topmost request is **accepted without error** and then silently dropped.
Measured on GNOME/Wayland via XWayland (with Tk, before ADR-030), reading the
attribute back gave 0; under a plain X server, the same call on the same
machine gave 1. Flet's `always_on_top` meets the same compositor.

Nothing in the code can detect that from the call, so the agent has to
reason about the session instead -- and say so, rather than promise
something it will not deliver.

Detection is fail-safe by construction: an environment it does not
recognise is "unknown", never a reason to refuse to start. An agent that
will not run because it cannot classify a desktop is strictly worse than
one that runs and says it is not sure.
"""

from __future__ import annotations

from vigia_eew.agent_state import AgentState, detect_presentation_environment


def _detect(platform: str, **environ: str):
    return detect_presentation_environment(environ=environ, platform=platform)


def test_wayland_is_declared_degraded() -> None:
    """CA-106.1: where the guarantee does not hold, and why."""
    env = _detect("linux", XDG_SESSION_TYPE="wayland", WAYLAND_DISPLAY="wayland-0")
    assert env.guarantee == "degraded"
    assert env.session == "wayland"
    assert "topmost" in env.reason.lower()


def test_x11_is_declared_guaranteed() -> None:
    """CA-106.1: on X11 the attribute sticks, which is what was measured."""
    env = _detect("linux", XDG_SESSION_TYPE="x11", DISPLAY=":0")
    assert env.guarantee == "guaranteed"
    assert env.session == "x11"


def test_windows_and_macos_are_guaranteed() -> None:
    """Both honour always-on-top for an ordinary application window."""
    assert _detect("win32").guarantee == "guaranteed"
    assert _detect("darwin").guarantee == "guaranteed"


def test_wayland_is_recognised_without_the_session_variable() -> None:
    """Some sessions do not export XDG_SESSION_TYPE; WAYLAND_DISPLAY still tells us.

    DISPLAY is not evidence of X11 on its own -- XWayland sets it too, which
    is precisely how an agent would conclude it was safe when it is not.
    """
    env = _detect("linux", WAYLAND_DISPLAY="wayland-0", DISPLAY=":0")
    assert env.guarantee == "degraded"


def test_an_unrecognised_environment_is_unknown_not_fatal() -> None:
    """CA-106.3: it starts anyway, and treats the guarantee as unconfirmed."""
    env = _detect("linux", XDG_SESSION_TYPE="something-new")
    assert env.guarantee == "unknown"
    assert env.reason


def test_a_bare_environment_is_unknown() -> None:
    """CA-106.3: no display at all -- a headless server, or a test runner."""
    assert _detect("linux").guarantee == "unknown"
    assert _detect("some-future-os").guarantee == "unknown"


def test_detection_never_raises() -> None:
    """CA-106.3: fail-safe. This runs at startup and must not be able to stop it."""
    for platform in ("linux", "win32", "darwin", "", "???"):
        for environ in ({}, {"XDG_SESSION_TYPE": ""}, {"WAYLAND_DISPLAY": ""}):
            assert detect_presentation_environment(environ=environ, platform=platform)


def test_the_agent_state_reports_the_guarantee() -> None:
    """CA-106.2: the user can see the limitation on their own machine."""
    state = AgentState(
        presentation=_detect("linux", XDG_SESSION_TYPE="wayland", WAYLAND_DISPLAY="wayland-0")
    )
    assert state.presentation.guarantee == "degraded"


def test_the_agent_state_detects_by_default() -> None:
    """Nobody has to remember to pass it in for the status to be truthful."""
    assert AgentState().presentation.guarantee in {"guaranteed", "degraded", "unknown"}


def test_the_tray_names_the_guarantee_of_this_session() -> None:
    """CA-106.2: the status the user opens shows the limitation, in their language."""
    from vigia_eew.i18n import t

    for guarantee in ("guaranteed", "degraded", "unknown"):
        for locale in ("en", "es"):
            text = t(f"tray_alert_{guarantee}", locale)
            assert text and not text.startswith("tray_alert_")
    assert "Wayland" in t("tray_alert_degraded", "en")


# --- T-181 · a drill never costs a real alert (REQ-UX-009, V-09) -------------------
#
# The scheduled drill changed the alert queue, the component the guarantee
# rests on. These are the two cases the Analyze asked to be pinned here.


def _event(event_id: str, source: str = "EMSC"):
    from datetime import UTC, datetime

    from vigia_eew.models import SeismicEvent

    return SeismicEvent(
        id=event_id,
        source=source,
        magnitude=6.1,
        mag_type="mw",
        lat=10.6,
        lon=-66.93,
        depth_km=10.0,
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=15.0,
        severity="critical",
    )


class _Window:
    def __init__(self, data, severity, on_acknowledge):
        self.data, self.on_acknowledge, self.closed = data, on_acknowledge, False

    def refresh(self, data):
        self.data = data

    def close(self):
        self.closed = True


def _controller(windows: list):
    from vigia_eew.notify.controller import AlertController

    def create(data, severity, on_acknowledge):
        windows.append(_Window(data, severity, on_acknowledge))
        return windows[-1]

    return AlertController(create_window=create)


def test_a_due_drill_waits_until_the_real_alerts_are_gone() -> None:
    """With a real alert shown or pending, a drill is not shown until the queue empties."""
    windows: list[_Window] = []
    ctrl = _controller(windows)
    ctrl.enqueue(_event("first"))
    ctrl.enqueue(_event("second"))

    assert ctrl.offer_drill(_event("SIM-0001", "SIMULATED")) is False
    windows[0].on_acknowledge()
    assert ctrl.offer_drill(_event("SIM-0001", "SIMULATED")) is False  # one still on screen
    assert [w.data.drill for w in windows] == [False, False]

    windows[1].on_acknowledge()
    assert ctrl.offer_drill(_event("SIM-0001", "SIMULATED")) is True
    assert windows[-1].data.drill is True


def test_a_real_alert_is_on_screen_without_the_drill_being_acknowledged() -> None:
    windows: list[_Window] = []
    ctrl = _controller(windows)
    ctrl.offer_drill(_event("SIM-0001", "SIMULATED"))

    ctrl.enqueue(_event("real"))

    assert windows[0].closed is True
    assert ctrl.alert_queue.current is not None and ctrl.alert_queue.current.id == "real"
    assert windows[1].data.drill is False
