"""Ingestion layer (RF-01..RF-06).

The sources (EMSC WebSocket, USGS REST, and FUNVISIS polling) publish **raw messages**
(`RawMessage`) onto an asyncio queue. The Phase 3 pipeline normalizes them into the
common `SeismicEvent`. Keeping the raw data here decouples the transport from the
normalization (API-SPEC §3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vigia_eew.models import Source


@dataclass(frozen=True, slots=True)
class RawMessage:
    """Unnormalized message emitted by a source.

    Attributes:
        source: origin of the message (`"EMSC"`, `"USGS"`, or `"FUNVISIS"`).
        action: `"create"` or `"update"` (EMSC provides it explicitly; USGS and
            FUNVISIS are always `"create"`).
        feature: the raw GeoJSON Feature object (with `properties` and `geometry`).
    """

    source: Source
    action: str
    feature: dict[str, Any]


__all__ = ["RawMessage"]
