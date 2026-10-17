"""Ingestion layer (RF-01..RF-06).

The sources (EMSC WebSocket, USGS REST, FUNVISIS polling, and GEOFON polling) publish
**raw messages** (`RawMessage`) onto an asyncio queue. The Phase 3 pipeline normalizes
them into the common `SeismicEvent`. Keeping the raw data here decouples the transport
from the normalization (API-SPEC §5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from vigia_eew.models import Source


def new_trace_id() -> str:
    """A fresh correlation id for one arrival (REQ-OBS-002, ADR-021).

    Short on purpose: it is read by a human scanning a log, not parsed. Eight
    hex characters is ~4 billion values, against a few tens of events alive at
    once -- a collision would have to happen inside one dedup window to matter.
    """
    return uuid.uuid4().hex[:8]


@dataclass(frozen=True, slots=True)
class RawMessage:
    """Unnormalized message emitted by a source.

    Attributes:
        source: origin of the message (`"EMSC"`, `"USGS"`, `"FUNVISIS"`, or `"GEOFON"`).
        action: `"create"` or `"update"` (EMSC provides it explicitly; USGS, FUNVISIS,
            and GEOFON are always `"create"`).
        feature: the raw payload — a GeoJSON Feature (with `properties`/`geometry`) for
            EMSC/USGS/FUNVISIS, or a `{column: value}` dict for a GEOFON text row.
        trace_id: correlation id for this arrival, generated here because this is
            where the journey starts. A payload discarded as malformed never
            reaches the normalizer, and that discard is exactly what somebody
            will later want to search for.
    """

    source: Source
    action: str
    feature: dict[str, Any]
    trace_id: str = field(default_factory=new_trace_id)


__all__ = ["RawMessage", "new_trace_id"]
