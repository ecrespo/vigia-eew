"""Event normalizer (RF-07, RF-08, RF-13; mapping in API-SPEC §5.1).

`Normalizer` turns a `RawMessage` into the common `SeismicEvent` that flows
through the rest of the pipeline. It no longer knows how any particular source
writes a timestamp or where it hides its id: **each source owns its own
translation** and the registry points at it (`ingest/registry.py`, ADR-022).

What is left here is what is genuinely common to every source and always
derived, never reported: the distance from the reference point, and the
severity band. Those are the invariants of the internal contract, so they
belong in one place rather than in four.

On invalid raw input it logs and returns `None` -- discard without aborting
(RNF-03). One malformed message from one network must not stop the other three.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from vigia_eew.config import ReferencePoint, Severity
from vigia_eew.geo import haversine_km
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.registry import SOURCE_REGISTRY, SourceSpec, UnknownSource, spec_for
from vigia_eew.models import Action, SeismicEvent, classify_severity


class Normalizer:
    """Converts `RawMessage` into `SeismicEvent`, routing by registered source."""

    def __init__(
        self,
        reference: ReferencePoint,
        severity: Severity,
        *,
        registry: tuple[SourceSpec, ...] = SOURCE_REGISTRY,
        logger: logging.Logger | None = None,
    ) -> None:
        self._reference = reference
        self._severity = severity
        self._registry = registry
        self._log = logger or logging.getLogger("vigia_eew.pipeline.normalize")

    def normalize(self, msg: RawMessage) -> SeismicEvent | None:
        """Normalizes a raw message into a `SeismicEvent`; returns None if invalid."""
        try:
            fields = spec_for(msg.source, self._registry).to_fields(msg)
            return self._build(fields, msg.action, msg.trace_id)
        except UnknownSource:
            # Composition validates the registry (`validate_registry`), so
            # reaching this means a message arrived from something that was
            # never wired -- worth a warning, not worth stopping the pipeline.
            self._log.warning(
                "normalize_unknown_source trace=%s source=%s", msg.trace_id, msg.source
            )
            return None
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            self._log.warning(
                "normalize_discarded trace=%s source=%s type=%s detail=%s",
                msg.trace_id,
                msg.source,
                type(exc).__name__,
                exc,
            )
            return None

    def _build(self, fields: dict[str, Any], action: str, trace_id: str) -> SeismicEvent:
        distance = haversine_km(
            self._reference.lat, self._reference.lon, fields["lat"], fields["lon"]
        )
        severity = classify_severity(
            fields["magnitude"], self._severity.info_max, self._severity.warning_max
        )
        valid_action: Action = "update" if action == "update" else "create"
        return SeismicEvent(
            **fields,
            trace_id=trace_id,
            distance_km=distance,
            severity=severity,
            action=valid_action,
        )
