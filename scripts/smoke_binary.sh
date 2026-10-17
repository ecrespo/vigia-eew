#!/usr/bin/env bash
#
# Run a freshly built binary and require it to work before it is published
# (REQ-OPS-008, CA-107.3, CA-107.4).
#
# Release v0.1.x shipped twice with a packaging resource that was only missing
# at *runtime* -- `bdc2a9d`. Nothing in the build noticed, because nothing in
# the build ever ran the thing it had just built. This does.
#
# Two modes, because what can be automated differs by platform:
#
#   --acknowledge   present the alert, send ENTER, require a clean exit. The
#                   full CA-107.3 check. Needs a display and xdotool.
#   (default)       present the alert, then terminate. Catches the missing
#                   resource, which is the failure that actually shipped.
#
# Usage: smoke_binary.sh [--acknowledge] <binary> [args...]

set -uo pipefail

ACKNOWLEDGE=0
if [[ "${1:-}" == "--acknowledge" ]]; then ACKNOWLEDGE=1; shift; fi
BIN="${1:?usage: smoke_binary.sh [--acknowledge] <binary> [args...]}"; shift

LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

echo "smoke: $BIN --simulate (acknowledge=$ACKNOWLEDGE)"
"$BIN" "$@" --simulate > "$LOG" 2>&1 &
PID=$!

# Wait for the alert to reach the screen, or for the process to die trying --
# a binary missing a resource dies here, which is the point.
# 240 x 0.25 s: the first run of a Flet binary unpacks its desktop client
# (ADR-030) before the window can exist, which on a cold runner takes seconds.
PRESENTED=0
for _ in $(seq 240); do
    # `alert_window_shown`, not `alert_presented`: the latter is logged before
    # the window is built, and v1.0.0's first tag passed it with a binary that
    # crashed drawing the alert (Flet's icon catalogue missing from the bundle).
    if grep -q "alert_window_shown" "$LOG"; then PRESENTED=1; break; fi
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
done

if [[ "$PRESENTED" -ne 1 ]]; then
    echo "FAIL: the binary never presented an alert" >&2
    sed -n '1,40p' "$LOG" >&2
    kill -9 "$PID" 2>/dev/null
    exit 1
fi
echo "  alert presented"

if [[ "$ACKNOWLEDGE" -ne 1 ]]; then
    kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null
    echo "  ok (presentation only; acknowledgement not automated on this platform)"
    exit 0
fi

# The alert window hides its title bar but keeps its title, so it is found by
# name and given focus first: under Xvfb there is no window manager to hand
# focus to a new window. ENTER acknowledges (the shell routes it to the alert),
# and acknowledging is the only way `--simulate` exits, so a clean exit *is*
# the assertion.
#
# Sent repeatedly rather than once, because `alert_window_shown` is logged when
# the controller has built the window and the window takes focus a moment
# later -- under Xvfb, with no window manager arbitrating, sometimes several
# moments later. A single keystroke into that gap goes nowhere and the smoke
# fails on a binary that is fine. Observed: two runs of the same binary, one
# pass and one failure. Extra keystrokes after the window is gone land on the
# root window and do nothing, so retrying costs nothing and removes the race.
for _ in $(seq 120); do
    kill -0 "$PID" 2>/dev/null || break
    WIN="$(xdotool search --name 'Vigía-eew' 2>/dev/null | tail -1)"
    if [[ -n "$WIN" ]]; then xdotool windowfocus "$WIN" 2>/dev/null; fi
    xdotool key --clearmodifiers Return 2>/dev/null
    sleep 0.25
done
if kill -0 "$PID" 2>/dev/null; then
    echo "FAIL: the alert was presented but never acknowledged; the agent did not exit" >&2
    kill -9 "$PID" 2>/dev/null
    exit 1
fi

wait "$PID"; RC=$?
if [[ "$RC" -ne 0 ]]; then
    echo "FAIL: exited $RC after acknowledgement" >&2
    sed -n '1,40p' "$LOG" >&2
    exit 1
fi
echo "  acknowledged, exited cleanly"
