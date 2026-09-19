"""Declarative registry of the agent's sources (REQ-ING-009, ADR-022).

Adding a source used to mean three separate edits in three different shapes:
a branch in the normalizer's `if source ==` ladder, a factory inside
`Application._build_supervisor`, and whatever else happened to enumerate the
four. Nothing enforced that you found all of them, and nothing complained if
you did not -- the agent started, looked healthy, and was blind in one
direction.

A source is now one declaration: what it is called, when it is enabled, how
to run it, and how to translate what it produces. The translation lives with
the source module itself (`ws_emsc.to_fields`, and so on), because that is
where the foreign vocabulary is already understood; the registry only points
at it.

`SIMULATED` is deliberately absent. It is a source of the domain model but
not an ingested one -- `simulation.py` injects it for `--simulate` and there
is nothing to poll.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vigia_eew.config import by_priority
from vigia_eew.ingest import RawMessage, rest_funvisis, rest_geofon, rest_usgs, ws_emsc

if TYPE_CHECKING:
    from vigia_eew.agent_state import AgentState
    from vigia_eew.config import Settings, SourceSettings
    from vigia_eew.models import Source
    from vigia_eew.state import StateStore

#: A supervised task: a no-argument factory producing the coroutine to run.
TaskFactory = Callable[[], Awaitable[Any]]


class UnknownSource(LookupError):
    """A source with no entry in the registry.

    Raised at composition rather than swallowed per message: an agent running
    with one of its four networks quietly missing is the failure this exists
    to prevent.
    """


@dataclass(frozen=True, slots=True)
class IngestContext:
    """Everything a source needs in order to be built.

    Bundled rather than passed one argument at a time so that adding a
    dependency does not change five call sites and four signatures.
    """

    cfg: Settings
    state: StateStore
    queue: asyncio.Queue[RawMessage]
    agent_state: AgentState | None = None


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One source, declared once.

    Attributes:
        source: the value that appears in `RawMessage.source` and in the event.
        task_name: the name the supervisor reports it under.
        settings_of: finds this source's own section of the configuration.
            One accessor rather than one per question, so that `enabled` and
            `priority` cannot come to disagree about which section they read.
        make_task: builds the supervised coroutine factory from the context.
        to_fields: translates a raw payload into the internal contract's
            fields -- the anti-corruption layer for this source's format.
    """

    source: Source
    task_name: str
    settings_of: Callable[[Settings], SourceSettings]
    make_task: Callable[[IngestContext], TaskFactory]
    to_fields: Callable[[RawMessage], dict[str, Any]]

    def is_enabled(self, cfg: Settings) -> bool:
        """Whether this source runs at all (RF-12)."""
        return self.settings_of(cfg).enabled

    def priority(self, cfg: Settings) -> int | None:
        """Declared preference between sources, or None when the file declares none."""
        return self.settings_of(cfg).priority


def _emsc_task(ctx: IngestContext) -> TaskFactory:
    return lambda: ws_emsc.WSIngestor(ctx.cfg.sources_emsc, ctx.queue, state=ctx.agent_state).run()


def _usgs_task(ctx: IngestContext) -> TaskFactory:
    return lambda: rest_usgs.RESTReconciler(
        ctx.cfg.sources_usgs,
        ctx.cfg.reference,
        ctx.cfg.filter,
        ctx.state,
        ctx.queue,
        timezone=ctx.cfg.notification.timezone,
    ).run()


def _funvisis_task(ctx: IngestContext) -> TaskFactory:
    return lambda: rest_funvisis.FUNVISISPoller(ctx.cfg.sources_funvisis, ctx.queue).run()


def _geofon_task(ctx: IngestContext) -> TaskFactory:
    return lambda: rest_geofon.GEOFONPoller(
        ctx.cfg.sources_geofon,
        ctx.cfg.reference,
        ctx.cfg.filter,
        ctx.state,
        ctx.queue,
        timezone=ctx.cfg.notification.timezone,
    ).run()


#: Registration order is the order the supervisor reports tasks in.
SOURCE_REGISTRY: tuple[SourceSpec, ...] = (
    SourceSpec(
        source="EMSC",
        task_name="ws",
        settings_of=lambda cfg: cfg.sources_emsc,
        make_task=_emsc_task,
        to_fields=ws_emsc.to_fields,
    ),
    SourceSpec(
        source="USGS",
        task_name="rest",
        settings_of=lambda cfg: cfg.sources_usgs,
        make_task=_usgs_task,
        to_fields=rest_usgs.to_fields,
    ),
    SourceSpec(
        source="FUNVISIS",
        task_name="funvisis",
        settings_of=lambda cfg: cfg.sources_funvisis,
        make_task=_funvisis_task,
        to_fields=rest_funvisis.to_fields,
    ),
    SourceSpec(
        source="GEOFON",
        task_name="geofon",
        settings_of=lambda cfg: cfg.sources_geofon,
        make_task=_geofon_task,
        to_fields=rest_geofon.to_fields,
    ),
)

#: Sources the agent ingests. `SIMULATED` is excluded by design, see the module
#: docstring; keeping the set explicit is what lets `validate_registry` tell a
#: deliberate absence from a forgotten one.
INGESTED_SOURCES: frozenset[str] = frozenset({"EMSC", "USGS", "FUNVISIS", "GEOFON"})


def spec_for(source: str, registry: tuple[SourceSpec, ...] = SOURCE_REGISTRY) -> SourceSpec:
    """The spec for `source`, or `UnknownSource` naming it."""
    for spec in registry:
        if spec.source == source:
            return spec
    raise UnknownSource(f"no source spec registered for {source!r}")


def validate_registry(registry: tuple[SourceSpec, ...] = SOURCE_REGISTRY) -> None:
    """Fails composition if an ingested source has no spec.

    Called while wiring the agent, not per message. A missing spec would
    otherwise surface as events silently discarded by the normalizer, which
    looks like a quiet network rather than a broken build.
    """
    missing = INGESTED_SOURCES - {spec.source for spec in registry}
    if missing:
        raise UnknownSource(f"source spec missing from the registry: {', '.join(sorted(missing))}")


def ordered_sources(
    cfg: Settings, registry: tuple[SourceSpec, ...] = SOURCE_REGISTRY
) -> tuple[SourceSpec, ...]:
    """The sources in the order of preference the configuration declares.

    Ranked sources first, ascending; the rest after them, in the order the
    registry declares them. That is what makes a `config.toml` from v0.6.0 --
    which declares no priorities at all -- mean exactly what it used to
    (CA-110.6).

    This is **not** the order the sources are queried in. Serialising the
    queries by priority would delay the alert, so the supervisor keeps
    registering them in registry order and they stay concurrent and
    independent (ADR-026, CA-110.7).
    """
    return tuple(by_priority([(spec, spec.priority(cfg)) for spec in registry]))


def priority_rank(
    cfg: Settings, registry: tuple[SourceSpec, ...] = SOURCE_REGISTRY
) -> dict[str, int]:
    """Each source's position in the preference order; smaller wins.

    Dense on purpose. The deduplicator compares two sources and needs an
    answer for both, whatever gaps the user left between the numbers they
    typed -- and a source with no declared priority still has to be
    comparable to one that has.
    """
    return {spec.source: position for position, spec in enumerate(ordered_sources(cfg, registry))}
