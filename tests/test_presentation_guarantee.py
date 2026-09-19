"""Tests for the declared scope of the alert guarantee (REQ-ALE-003, HU-106).

The product promises an alert that cannot be ignored. On Wayland it cannot
keep that promise through Tkinter, and the way it fails is the problem:
`wm_attributes("-topmost", True)` is **accepted without error** and then
silently dropped. Measured on GNOME/Wayland via XWayland, reading the
attribute back gives 0; under a plain X server, the same call on the same
machine gives 1.

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
