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
PRESENTED=0
for _ in $(seq 80); do
    if grep -q "alert_presented" "$LOG"; then PRESENTED=1; break; fi
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

# The window is overrideredirect, so it has no entry a window manager could
# name -- it is found by having focus, not by title. ENTER acknowledges
# (configure_undismissable), and acknowledging is the only way `--simulate`
# exits, so a clean exit *is* the assertion.
xdotool key --clearmodifiers Return 2>/dev/null

for _ in $(seq 40); do kill -0 "$PID" 2>/dev/null || break; sleep 0.25; done
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
