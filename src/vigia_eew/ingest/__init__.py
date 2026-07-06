"""Ingestion layer (RF-01..RF-06).

The sources (EMSC WebSocket, USGS REST, FUNVISIS polling, and GEOFON polling) publish
**raw messages** (`RawMessage`) onto an asyncio queue. The Phase 3 pipeline normalizes
them into the common `SeismicEvent`. Keeping the raw data here decouples the transport
from the normalization (API-SPEC §5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vigia_eew.models import Source


@dataclass(frozen=True, slots=True)
class RawMessage:
    """Unnormalized message emitted by a source.

    Attributes:
        source: origin of the message (`"EMSC"`, `"USGS"`, `"FUNVISIS"`, or `"GEOFON"`).
        action: `"create"` or `"update"` (EMSC provides it explicitly; USGS, FUNVISIS,
            and GEOFON are always `"create"`).
        feature: the raw payload — a GeoJSON Feature (with `properties`/`geometry`) for
            EMSC/USGS/FUNVISIS, or a `{column: value}` dict for a GEOFON text row.
    """

    source: Source
    action: str
    feature: dict[str, Any]


__all__ = ["RawMessage"]
