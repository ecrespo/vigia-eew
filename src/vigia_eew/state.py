"""State persistence (RF-06, RF-10).

`StateStore` saves and loads `AppState` as JSON with **atomic writes** (temp
file + `os.replace`) so a crash never corrupts the file. It keeps the
`alerted_ids` (to avoid repeating alerts after restarts, RF-10) and the
`cursor_usgs` (to reconcile without reprocessing history, RF-06). Applies
pruning by age.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from platformdirs import user_data_dir

from vigia_eew.config import APP_NAME, ReferencePoint
from vigia_eew.models import AlertedId, AppState, DetectedLocation, EventSignature

STATE_FILE_NAME = "state.json"
# Maximum age of ids/signatures before pruning them (DATA-MODEL §2.2).
MAX_AGE = timedelta(hours=24)


def default_state_path() -> Path:
    """Path to `state.json` in the user's data directory (cross-platform)."""
    return Path(user_data_dir(APP_NAME)) / STATE_FILE_NAME


class StateStore:
    """Persistent state store with atomic writes."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_state_path()
        self._state: AppState = AppState()

    @property
    def state(self) -> AppState:
        return self._state

    def load(self) -> AppState:
        """Loads the state from disk. If missing or corrupt, starts fresh.

        The robustness here is deliberate (RNF-03): a corrupt `state.json` must not
        prevent the agent from starting; it's discarded and the state is reset.
        """
        if not self.path.exists():
            self._state = AppState()
            return self._state
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._state = AppState.model_validate(data)
        except (json.JSONDecodeError, ValueError, OSError):
            # Corrupt or unreadable state: start clean instead of failing.
            self._state = AppState()
        return self._state

    def save(self) -> None:
        """Persists the state to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # pydantic v2: JSON serialization with ISO-8601 datetimes.
        content = self._state.model_dump_json(indent=2)
        # Atomic write: write to a temp file in the same directory and replace.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, self.path)  # atomic on the same filesystem
        except BaseException:
            # Clean up the temp file if something fails before the replace.
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # --- Domain operations ---

    def already_alerted(self, event_id: str) -> bool:
        """Indicates whether an event id was already alerted (RF-10)."""
        return any(a.id == event_id for a in self._state.alerted_ids)

    def register_alerted(self, alert: AlertedId) -> None:
        """Adds an alerted id if it wasn't already present."""
        if not self.already_alerted(alert.id):
            self._state.alerted_ids.append(alert)

    def mark_acknowledged(self, event_id: str, when: datetime | None = None) -> None:
        """Records the acknowledgment of an alert (audit trail, OBJ-1)."""
        when = when or datetime.now(UTC)
        for a in self._state.alerted_ids:
            if a.id == event_id:
                a.acknowledged_utc = when
                break

    def add_signature(self, signature: EventSignature) -> None:
        """Stores a recent signature for inter-source dedup (RF-09)."""
        self._state.recent_signatures.append(signature)

    def update_usgs_cursor(self, cursor_ms: int) -> None:
        """Advances the USGS cursor to the highest value seen (RF-06)."""
        current = self._state.cursor_usgs_ms
        if current is None or cursor_ms > current:
            self._state.cursor_usgs_ms = cursor_ms

    def update_geofon_cursor(self, cursor_ms: int) -> None:
        """Advances the GEOFON cursor to the highest value seen (RF-39, RF-06)."""
        current = self._state.cursor_geofon_ms
        if current is None or cursor_ms > current:
            self._state.cursor_geofon_ms = cursor_ms

    def cached_location(self) -> ReferencePoint | None:
        """Last IP-detected and cached location, if any (RF-33)."""
        loc = self._state.detected_location
        if loc is None:
            return None
        return ReferencePoint(name=loc.name, lat=loc.lat, lon=loc.lon)

    def cache_location(self, reference: ReferencePoint, *, when: datetime | None = None) -> None:
        """Persists an IP-detected location to avoid repeating the call on restart."""
        self._state.detected_location = DetectedLocation(
            name=reference.name,
            lat=reference.lat,
            lon=reference.lon,
            detected_utc=when or datetime.now(UTC),
        )

    def prune(self, now: datetime | None = None) -> None:
        """Removes ids and signatures older than `MAX_AGE` (DATA-MODEL §2.2)."""
        now = now or datetime.now(UTC)
        cutoff = now - MAX_AGE
        self._state.alerted_ids = [a for a in self._state.alerted_ids if a.time_utc >= cutoff]
        self._state.recent_signatures = [
            f for f in self._state.recent_signatures if f.time_utc >= cutoff
        ]
