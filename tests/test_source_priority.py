"""Tests for the declared priority between networks (T-139, REQ-ING-011, HU-110).

Priority answers one question and deliberately not another: **whose data
prevails** when the same earthquake arrives twice, never **whether** to alert.
The tests that draw that line live with the deduplicator (T-140); these cover
the declaration itself -- where it is read from, what an older file means, and
that declaring it changes nothing about how the sources are queried.
"""

from __future__ import annotations

from vigia_eew.config import (
    EMSCSource,
    FUNVISISSource,
    GEOFONSource,
    Settings,
    USGSSource,
)
from vigia_eew.ingest.registry import (
    SOURCE_REGISTRY,
    ordered_sources,
    priority_rank,
    spec_for,
)


def _with_priorities(**by_source: int | None) -> Settings:
    """Settings whose four sources carry the priorities given."""
    return Settings(
        sources_emsc=EMSCSource(priority=by_source.get("emsc")),
        sources_usgs=USGSSource(priority=by_source.get("usgs")),
        sources_funvisis=FUNVISISSource(priority=by_source.get("funvisis")),
        sources_geofon=GEOFONSource(priority=by_source.get("geofon")),
    )


# --- The declaration ------------------------------------------------------------


def test_each_source_reads_its_own_priority() -> None:
    """The spec knows where its source's settings live; nothing else has to."""
    cfg = _with_priorities(emsc=2, funvisis=1)
    assert spec_for("EMSC").priority(cfg) == 2
    assert spec_for("FUNVISIS").priority(cfg) == 1
    assert spec_for("GEOFON").priority(cfg) is None


def test_the_same_accessor_answers_enabled() -> None:
    """One accessor per source, two questions -- not two lambdas that can drift."""
    cfg = Settings(sources_geofon=GEOFONSource(enabled=False, priority=3))
    assert spec_for("GEOFON").is_enabled(cfg) is False
    assert spec_for("GEOFON").priority(cfg) == 3


# --- CA-110.6 · A file from before priorities existed ----------------------------


def test_a_configuration_without_priorities_is_still_valid() -> None:
    """A `config.toml` from v0.6.0 declares none of this and must still load."""
    cfg = Settings()
    assert all(spec.priority(cfg) is None for spec in SOURCE_REGISTRY)
    assert [spec.source for spec in ordered_sources(cfg)] == [
        spec.source for spec in SOURCE_REGISTRY
    ]


def test_sources_without_a_declared_priority_go_last() -> None:
    """Undeclared means unranked, not excluded -- the network still runs."""
    cfg = _with_priorities(geofon=1, usgs=2)
    assert [spec.source for spec in ordered_sources(cfg)] == [
        "GEOFON",
        "USGS",
        "EMSC",
        "FUNVISIS",
    ]


def test_undeclared_sources_keep_the_order_they_were_registered_in() -> None:
    """Their relative order is the declaration order, not the dictionary's whim."""
    cfg = _with_priorities(funvisis=1)
    assert [spec.source for spec in ordered_sources(cfg)] == [
        "FUNVISIS",
        "EMSC",
        "USGS",
        "GEOFON",
    ]


def test_the_declared_order_is_what_the_numbers_say() -> None:
    cfg = _with_priorities(emsc=4, usgs=3, funvisis=2, geofon=1)
    assert [spec.source for spec in ordered_sources(cfg)] == [
        "GEOFON",
        "FUNVISIS",
        "USGS",
        "EMSC",
    ]


def test_the_numbers_need_not_be_consecutive() -> None:
    """Reordering a list of four should not force a renumbering of all of them."""
    cfg = _with_priorities(emsc=10, funvisis=2)
    assert [spec.source for spec in ordered_sources(cfg)][:2] == ["FUNVISIS", "EMSC"]


# --- The rank the deduplicator consumes ------------------------------------------


def test_the_rank_is_dense_and_covers_every_source() -> None:
    """The deduplicator compares ranks, so every source needs one, gaps or not."""
    rank = priority_rank(_with_priorities(emsc=10, funvisis=2))
    assert set(rank) == {"EMSC", "USGS", "FUNVISIS", "GEOFON"}
    assert sorted(rank.values()) == [0, 1, 2, 3]
    assert rank["FUNVISIS"] < rank["EMSC"] < rank["USGS"] < rank["GEOFON"]


def test_with_nothing_declared_the_rank_follows_the_registry() -> None:
    rank = priority_rank(Settings())
    assert rank["EMSC"] < rank["USGS"] < rank["FUNVISIS"] < rank["GEOFON"]


# --- CA-110.7 · Priority does not touch how the sources are queried ---------------


def test_the_supervisor_still_registers_tasks_in_registry_order(tmp_path) -> None:
    """Serialising the queries by priority would delay the alert (ADR-026).

    The four sources stay concurrent and independent; priority resolves data
    after the fact, which is the whole of what it is allowed to do.
    """
    import asyncio

    from vigia_eew.agent_state import AgentState
    from vigia_eew.state import StateStore
    from vigia_eew.wiring import Wiring

    inverted = _with_priorities(emsc=4, usgs=3, funvisis=2, geofon=1)
    wiring = Wiring(inverted, StateStore(tmp_path / "state.json"), AgentState())
    queue: asyncio.Queue = asyncio.Queue()
    processor = wiring.build_processor(queue, on_alert=lambda _e: None, on_update=lambda _e: None)

    sup = wiring.build_supervisor(queue, processor)

    assert sup.names == ["ws", "rest", "funvisis", "geofon", "pipeline"]


def test_a_disabled_source_is_still_left_out_whatever_its_priority(tmp_path) -> None:
    """CA-110.5: the enable flag decides existence; priority only orders."""
    import asyncio

    from vigia_eew.agent_state import AgentState
    from vigia_eew.state import StateStore
    from vigia_eew.wiring import Wiring

    cfg = _with_priorities(emsc=2, funvisis=1)
    cfg.sources_funvisis.enabled = False
    wiring = Wiring(cfg, StateStore(tmp_path / "state.json"), AgentState())
    queue: asyncio.Queue = asyncio.Queue()
    processor = wiring.build_processor(queue, on_alert=lambda _e: None, on_update=lambda _e: None)

    sup = wiring.build_supervisor(queue, processor)

    assert "funvisis" not in sup.names
    assert "ws" in sup.names
