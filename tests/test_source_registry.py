"""Tests for the declarative source registry (REQ-ING-009, HU-104).

Adding a source used to mean editing the normalizer's `if source ==` ladder,
adding a factory to `Application._build_supervisor`, and finding every other
place that enumerated the four. The registry makes a source one declaration:
what it is called, when it is enabled, how to run it, and how to translate
what it produces.

That last part is the anti-corruption layer, and it belongs with the adapter
that speaks the foreign language -- each source module owns its own mapping,
not a central branch that has to know all four dialects at once.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from vigia_eew.config import Settings
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.registry import (
    SOURCE_REGISTRY,
    IngestContext,
    SourceSpec,
    UnknownSource,
    spec_for,
    validate_registry,
)
from vigia_eew.models import Source
from vigia_eew.state import StateStore

#: `SIMULATED` is a source of the domain model but not an ingested one: it is
#: injected by `simulation.py` for `--simulate` and has no ingestor by design.
INGESTED = {"EMSC", "USGS", "FUNVISIS", "GEOFON"}


def _context(tmp_path) -> IngestContext:
    return IngestContext(
        cfg=Settings(),
        state=StateStore(tmp_path / "state.json"),
        queue=asyncio.Queue(),
    )


def test_every_ingested_source_is_registered() -> None:
    """CA-104.3: the registry is complete against the domain's source type."""
    assert {spec.source for spec in SOURCE_REGISTRY} == INGESTED
    validate_registry()


def test_the_simulated_source_is_deliberately_absent() -> None:
    """`SIMULATED` has no ingestor, and that is a decision, not an omission."""
    declared = set(Source.__args__)  # type: ignore[attr-defined]
    assert declared - INGESTED == {"SIMULATED"}
    assert "SIMULATED" not in {spec.source for spec in SOURCE_REGISTRY}


def test_an_unregistered_source_fails_loudly() -> None:
    """CA-104.3: it names the source instead of running on quietly without it."""
    with pytest.raises(UnknownSource, match="MADEUP"):
        spec_for("MADEUP")


def test_an_incomplete_registry_fails_at_composition() -> None:
    """CA-104.3: a source that lost its spec stops startup, naming it.

    Silently running with one of four networks missing is the failure mode
    worth preventing: the agent looks healthy and is blind in one direction.
    """
    without_geofon = tuple(s for s in SOURCE_REGISTRY if s.source != "GEOFON")
    with pytest.raises(UnknownSource, match="GEOFON"):
        validate_registry(without_geofon)


def test_each_source_translates_its_own_payload(tmp_path) -> None:
    """CA-104.2: the mapping comes from the registry, not from a central ladder."""
    msg = RawMessage(
        source="GEOFON",
        action="create",
        feature={
            "EventID": "gfz2026abcd",
            "Magnitude": "5.4",
            "MagType": "mb",
            "EventLocationName": "OFFSHORE  SUCRE,  VENEZUELA",
            "Latitude": "10.7",
            "Longitude": "-63.2",
            "Depth/km": "31.0",
            "Time": "2026-09-19T12:00:00Z",
        },
    )
    fields = spec_for("GEOFON").to_fields(msg)
    assert fields["id"] == "gfz2026abcd"
    assert fields["magnitude"] == 5.4
    assert fields["time_utc"] == datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def test_a_new_source_needs_only_its_own_declaration(tmp_path) -> None:
    """CA-104.1/CA-104.2: a source added to the registry works end to end.

    Neither the normalizer nor the supervisor wiring is touched here. That is
    the whole promise: the registry, the ingestor and its test.
    """
    from vigia_eew.pipeline.normalize import Normalizer

    def to_fields(msg: RawMessage) -> dict[str, Any]:
        return {
            "id": msg.feature["id"],
            "source": "EMSC",  # reuses an existing literal; the point is the routing
            "magnitude": 4.2,
            "mag_type": "ml",
            "place": "Test",
            "region": None,
            "lat": 10.0,
            "lon": -66.0,
            "depth_km": 10.0,
            "time_utc": datetime(2026, 9, 19, tzinfo=UTC),
            "lastupdate_utc": None,
        }

    spec = SourceSpec(
        source="TESTNET",  # type: ignore[arg-type]
        task_name="testnet",
        settings_of=lambda cfg: cfg.sources_emsc,
        make_task=lambda ctx: lambda: asyncio.sleep(0),
        to_fields=to_fields,
    )
    cfg = Settings()
    normalizer = Normalizer(cfg.reference, cfg.severity, registry=(*SOURCE_REGISTRY, spec))

    event = normalizer.normalize(
        RawMessage(source="TESTNET", action="create", feature={"id": "t-1"})  # type: ignore[arg-type]
    )

    assert event is not None
    assert event.id == "t-1"
    assert event.distance_km is not None


def test_a_disabled_source_produces_no_task(tmp_path) -> None:
    """CA-104.6: disabling stays one line of configuration."""
    from vigia_eew.config import GEOFONSource

    ctx = _context(tmp_path)
    enabled = [s.task_name for s in SOURCE_REGISTRY if s.is_enabled(ctx.cfg)]
    assert "geofon" in enabled

    off = Settings(sources_geofon=GEOFONSource(enabled=False))
    still_on = [s.task_name for s in SOURCE_REGISTRY if s.is_enabled(off)]
    assert "geofon" not in still_on
    assert still_on == [name for name in enabled if name != "geofon"]
