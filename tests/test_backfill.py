"""Tests for the recovery of a period into the history (T-170, REQ-HIS-010..012, ADR-036).

The history only knows what the agent saw while it was running. The recovery
completes it from the networks' catalogues -- and the whole design of it is
about what it must **not** do: alert on an earthquake from a month ago,
overwrite what the agent decided at the time, turn one earthquake into two,
or touch anything but the history file.

The catalogues are a fake client keyed by URL; the store is a real SQLite
file, for the reason `test_history.py` gives.
"""

from __future__ import annotations

import ast
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from vigia_eew import backfill
from vigia_eew.backfill import Outcome, PeriodRefused, describe, exit_code, recover
from vigia_eew.config import Settings
from vigia_eew.history import EventRecord, HistoryQuery, HistoryStore

_NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
_QUAKE = _NOW - timedelta(days=10)

_GEOFON_HEADER = (
    "#EventID|Time|Latitude|Longitude|Depth/km|Author|Catalog|Contributor|ContributorID|"
    "MagType|Magnitude|MagAuthor|EventLocationName|EventType"
)


def _emsc(unid: str, *, when: datetime = _QUAKE, mag: float = 4.6, lat: float = 10.6) -> dict:
    return {
        "id": unid,
        "properties": {
            "unid": unid,
            "time": when.strftime("%Y-%m-%dT%H:%M:%S.0Z"),
            "lat": lat,
            "lon": -66.9,
            "depth": 12.0,
            "mag": mag,
            "magtype": "mb",
            "flynn_region": "NEAR COAST OF VENEZUELA",
        },
    }


def _usgs(event_id: str, *, when: datetime = _QUAKE, mag: float = 4.7, lat: float = 10.65) -> dict:
    return {
        "id": event_id,
        "properties": {
            "mag": mag,
            "magType": "mb",
            "place": "10 km N of Caracas, Venezuela",
            "time": int(when.timestamp() * 1000),
        },
        "geometry": {"coordinates": [-66.9, lat, 12.0]},
    }


def _geofon(event_id: str, *, when: datetime = _QUAKE, mag: float = 4.5) -> str:
    moment = when.strftime("%Y-%m-%dT%H:%M:%S")
    return (
        f"{event_id}|{moment}|10.62|-66.9|12.0|GFZ|||{event_id}|mb|{mag}|GFZ|Venezuela|earthquake"
    )


class _Resp:
    def __init__(self, status: int = 200, *, features=None, text: str = "") -> None:
        self.status_code = status
        self._features = features
        self.text = text
        self.headers: dict[str, str] = {}

    def json(self):
        return {"type": "FeatureCollection", "features": self._features or []}


class _Catalogues:
    """The three services, answering by URL. A network not given answers "nothing"."""

    def __init__(self, cfg: Settings, *, emsc=None, usgs=None, geofon=None) -> None:
        self._answers = {
            cfg.sources_emsc.catalog_url: emsc,
            cfg.sources_usgs.url: usgs,
            cfg.sources_geofon.url: geofon,
        }
        self.calls: list[str] = []

    async def get(self, url, *, params=None, timeout=None, headers=None):
        self.calls.append(url)
        answer = self._answers.get(url)
        if answer is None:
            return _Resp(204)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, _Resp):
            return answer
        if isinstance(answer, str):
            return _Resp(text=_GEOFON_HEADER + "\n" + answer)
        return _Resp(features=answer)


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.fixture
def cfg() -> Settings:
    return Settings()


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    made = HistoryStore(tmp_path / "history.sqlite3", prune_on_open=False).open()
    yield made
    made.close()


async def _recover(cfg, store, client, *, days: int = 30, **kwargs) -> list[Outcome]:
    return await recover(
        cfg, store, days, client=client, now=lambda: _NOW, sleep=_no_sleep, **kwargs
    )


def _by_source(outcomes: list[Outcome]) -> dict[str, Outcome]:
    return {outcome.source: outcome for outcome in outcomes}


def _live(**overrides) -> EventRecord:
    """A row the agent wrote while running."""
    fields: dict = {
        "correlation_id": "live-1",
        "source": "EMSC",
        "source_event_id": "emsc-1",
        "occurred_at": _QUAKE,
        "recorded_at": _QUAKE + timedelta(seconds=40),
        "latitude": 10.6,
        "longitude": -66.9,
        "depth_km": 12.0,
        "magnitude": 4.6,
        "region": "AS THE AGENT SAW IT",
        "distance_km": 14.0,
        "severity": "warning",
        "verdict": "alerted",
        "reason": None,
    }
    fields.update(overrides)
    return EventRecord(**fields)


# --- CA-117.1, CA-117.4 · an empty history is completed, as recovered ---------------


async def test_an_empty_history_is_completed_from_the_three_networks(cfg, store) -> None:
    far = _QUAKE - timedelta(days=3)
    client = _Catalogues(
        cfg,
        emsc=[_emsc("emsc-1")],
        usgs=[_usgs("us-far", when=far)],
        geofon=_geofon("gfz-other", when=far - timedelta(days=2)),
    )

    outcomes = await _recover(cfg, store, client)

    rows = store.rows()
    assert sorted(row.source for row in rows) == ["EMSC", "GEOFON", "USGS"]
    assert {row.verdict for row in rows} == {"recovered"}
    assert all(row.reason is None and row.severity is None for row in rows)
    assert all(_NOW - timedelta(days=30) <= row.occurred_at <= _NOW for row in rows)
    assert [(o.source, o.status, o.recovered) for o in outcomes if o.status == "recovered"] == [
        ("EMSC", "recovered", 1),
        ("USGS", "recovered", 1),
        ("GEOFON", "recovered", 1),
    ]


async def test_a_recovered_row_carries_the_distance_from_here_and_when_it_was_recovered(
    cfg, store
) -> None:
    await _recover(cfg, store, _Catalogues(cfg, emsc=[_emsc("emsc-1")]))

    (row,) = store.rows()
    assert row.recorded_at == _NOW
    assert 0 < row.distance_km < 30  # Caracas, the default reference, is next door
    assert row.region == "NEAR COAST OF VENEZUELA"
    assert row.correlation_id  # minted: it starts an earthquake of its own


# --- CA-117.2 · it says what it could not recover -----------------------------------


async def test_the_outcome_names_every_configured_network(cfg, store) -> None:
    outcomes = _by_source(await _recover(cfg, store, _Catalogues(cfg)))

    assert set(outcomes) == {"EMSC", "USGS", "GEOFON", "FUNVISIS"}
    assert outcomes["FUNVISIS"].status == "not_recoverable"
    assert "no query by date" in outcomes["FUNVISIS"].detail


async def test_a_network_switched_off_is_neither_asked_nor_listed(store) -> None:
    cfg = Settings(sources_usgs={"enabled": False})
    client = _Catalogues(cfg)

    outcomes = _by_source(await _recover(cfg, store, client))

    assert "USGS" not in outcomes
    assert cfg.sources_usgs.url not in client.calls


# --- CA-117.5 · repeating it changes nothing ----------------------------------------


async def test_a_second_run_leaves_the_history_as_it_was(cfg, store) -> None:
    client = _Catalogues(cfg, emsc=[_emsc("emsc-1")], usgs=[_usgs("us-1")])
    await _recover(cfg, store, client)
    before = [(row.id, row.correlation_id, row.superseded_by) for row in store.rows()]

    again = _by_source(await _recover(cfg, store, client))

    assert [(row.id, row.correlation_id, row.superseded_by) for row in store.rows()] == before
    assert (again["EMSC"].recovered, again["EMSC"].present) == (0, 1)
    assert (again["USGS"].recovered, again["USGS"].present) == (0, 1)


# --- CA-117.6 · it does not reach beyond the retention ------------------------------


async def test_a_period_beyond_the_retention_is_refused_before_any_request(cfg, store) -> None:
    client = _Catalogues(cfg)

    with pytest.raises(PeriodRefused) as refusal:
        await _recover(cfg, store, client, days=400)

    assert client.calls == []
    assert "400" in str(refusal.value)
    assert "365" in str(refusal.value)
    assert "recovered_retention_days" in str(refusal.value)


async def test_the_retention_itself_can_be_asked_for(cfg, store) -> None:
    await _recover(cfg, store, _Catalogues(cfg), days=365)  # does not raise


@pytest.mark.parametrize("days", [0, -5])
async def test_a_period_of_no_days_is_refused(cfg, store, days: int) -> None:
    with pytest.raises(PeriodRefused):
        await _recover(cfg, store, _Catalogues(cfg), days=days)


# --- CA-117.7 · one network down does not stop the others ---------------------------


async def test_one_network_failing_leaves_the_others_recovered(cfg, store, caplog) -> None:
    client = _Catalogues(
        cfg,
        emsc=[_emsc("emsc-1")],
        usgs=[_usgs("us-far", when=_QUAKE - timedelta(days=3))],
        geofon=httpx.ReadTimeout("slow"),
    )

    with caplog.at_level(logging.WARNING, logger="vigia_eew.backfill"):
        outcomes = _by_source(await _recover(cfg, store, client))

    assert outcomes["EMSC"].status == outcomes["USGS"].status == "recovered"
    assert outcomes["GEOFON"].status == "failed"
    assert "timeout" in outcomes["GEOFON"].detail
    assert sorted(row.source for row in store.rows()) == ["EMSC", "USGS"]
    assert any("GEOFON" in record.getMessage() for record in caplog.records)


async def test_a_record_that_does_not_parse_is_skipped_and_counted(cfg, store) -> None:
    broken = {"id": "bad", "properties": {"unid": "bad"}}  # no time, no magnitude
    client = _Catalogues(cfg, emsc=[broken, _emsc("emsc-1")])

    outcomes = _by_source(await _recover(cfg, store, client))

    assert (outcomes["EMSC"].recovered, outcomes["EMSC"].skipped) == (1, 1)
    assert store.count() == 1


# --- CA-117.8 · what the agent decided is kept --------------------------------------


async def test_an_alerted_row_keeps_its_verdict_and_its_data(cfg, store) -> None:
    store.record(_live())
    revised = _emsc("emsc-1", mag=5.3)  # the catalogue has since revised it

    outcomes = _by_source(await _recover(cfg, store, _Catalogues(cfg, emsc=[revised])))

    (row,) = store.rows()
    assert (row.verdict, row.magnitude, row.region, row.severity) == (
        "alerted",
        4.6,
        "AS THE AGENT SAW IT",
        "warning",
    )
    assert (outcomes["EMSC"].recovered, outcomes["EMSC"].present) == (0, 1)


# --- CA-117.9 · an earthquake already known gains an arrival, not a twin -------------


async def test_the_same_earthquake_from_another_network_joins_it(cfg, store) -> None:
    prevailing = store.record(_live())

    await _recover(cfg, store, _Catalogues(cfg, usgs=[_usgs("us-1")]))

    per_earthquake = store.query(HistoryQuery(reading="earthquake"))
    arrivals = store.arrivals("live-1")
    assert [row.source for row in per_earthquake] == ["EMSC"]
    assert [(a.source, a.verdict) for a in arrivals] == [("EMSC", "alerted"), ("USGS", "recovered")]
    assert arrivals[1].superseded_by == prevailing


async def test_two_catalogues_reporting_one_earthquake_make_one_earthquake(cfg, store) -> None:
    """Both recovered in the same run: the better-ranked network's row prevails."""
    client = _Catalogues(cfg, emsc=[_emsc("emsc-1")], usgs=[_usgs("us-1")])

    await _recover(cfg, store, client)

    emsc, usgs = sorted(store.rows(), key=lambda row: row.source)
    assert emsc.correlation_id == usgs.correlation_id
    assert (emsc.superseded_by, usgs.superseded_by) == (None, emsc.id)
    assert store.count(HistoryQuery(reading="earthquake")) == 1


async def test_the_network_ranked_first_is_recovered_first_and_prevails(store) -> None:
    """Priority order (ADR-036 §3): with USGS ranked ahead, its row is the one that stands."""
    cfg = Settings(sources_usgs={"priority": 1}, sources_emsc={"priority": 2})
    client = _Catalogues(cfg, emsc=[_emsc("emsc-1")], usgs=[_usgs("us-1")])

    outcomes = await _recover(cfg, store, client)

    emsc, usgs = sorted(store.rows(), key=lambda row: row.source)
    assert [o.source for o in outcomes][:2] == ["USGS", "EMSC"]
    assert (usgs.superseded_by, emsc.superseded_by) == (None, usgs.id)


async def test_a_third_arrival_points_at_the_row_that_prevailed_not_at_the_second(
    cfg, store
) -> None:
    client = _Catalogues(cfg, emsc=[_emsc("emsc-1")], usgs=[_usgs("us-1")], geofon=_geofon("gfz-1"))

    await _recover(cfg, store, client)

    rows = {row.source: row for row in store.rows()}
    assert rows["GEOFON"].superseded_by == rows["EMSC"].id
    assert len({row.correlation_id for row in rows.values()}) == 1


async def test_earthquakes_that_are_not_the_same_stay_apart(cfg, store) -> None:
    store.record(_live())
    later = _usgs("us-later", when=_QUAKE + timedelta(minutes=10))  # an aftershock
    stronger = _usgs("us-strong", mag=6.0)  # same instant, but not the same event

    await _recover(cfg, store, _Catalogues(cfg, usgs=[later, stronger]))

    assert store.count(HistoryQuery(reading="earthquake")) == 3
    assert len(store.arrivals("live-1")) == 1


async def test_the_joining_uses_the_configured_thresholds(store) -> None:
    cfg = Settings(dedup={"magnitude_delta": 2.0})
    store.record(_live())

    await _recover(cfg, store, _Catalogues(cfg, usgs=[_usgs("us-strong", mag=6.0)]))

    assert store.count(HistoryQuery(reading="earthquake")) == 1


# --- CA-117.3, CA-117.11 · it touches the history and nothing else --------------------


async def test_the_operating_state_is_byte_for_byte_the_same(cfg, store, tmp_path) -> None:
    from vigia_eew.state import StateStore

    state_file = tmp_path / "state.json"
    state = StateStore(state_file)
    state.update_usgs_cursor(1_780_000_000_000)
    state.save()
    before = state_file.read_bytes()

    await _recover(cfg, store, _Catalogues(cfg, emsc=[_emsc("emsc-1")], usgs=[_usgs("us-1")]))

    assert state_file.read_bytes() == before


def _imports_of(module) -> set[str]:
    with open(module.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imported


def test_the_recovery_cannot_reach_anything_that_alerts() -> None:
    """CA-117.3 by construction: no path from here to a window, a sound or a toast.

    The import contract says the same in `pyproject.toml`; this is the copy
    that fails inside the test run.
    """
    imported = _imports_of(backfill)

    for forbidden in (
        "vigia_eew.notify",
        "vigia_eew.supervisor",
        "vigia_eew.state",
        "vigia_eew.pipeline.processor",
        "vigia_eew.pipeline.filter",
        "vigia_eew.app",
        "vigia_eew.wiring",
    ):
        assert not any(
            name == forbidden or name.startswith(forbidden + ".") for name in imported
        ), forbidden


def test_the_recovery_never_builds_a_deduplicator() -> None:
    """It shares the predicate, not the state: `Deduplicator` remembers what was alerted."""
    assert "vigia_eew.pipeline.dedup.Deduplicator" not in _imports_of(backfill)


# --- The outcome, as the command line reports it (03 §2) -----------------------------


def test_the_outcome_is_one_line_per_network() -> None:
    outcomes = [
        Outcome("EMSC", "recovered", recovered=109, present=12),
        Outcome("GEOFON", "failed", detail="timeout after 30 s"),
        Outcome(
            "FUNVISIS",
            "not_recoverable",
            detail="the service offers no query by date",
            reason_key="backfill_no_query_by_date",
        ),
    ]

    assert describe(outcomes, "en") == [
        "EMSC      recovered 109 · already present 12",
        "GEOFON    failed: timeout after 30 s",
        "FUNVISIS  not recoverable: the service offers no query by date",
    ]


def test_the_outcome_is_translated() -> None:
    lines = describe(
        [
            Outcome("EMSC", "recovered", recovered=3, present=0),
            Outcome("FUNVISIS", "not_recoverable", reason_key="backfill_no_query_by_date"),
        ],
        "es",
    )

    assert lines == [
        "EMSC      recuperados 3 · ya presentes 0",
        "FUNVISIS  no recuperable: el servicio no ofrece consulta por fecha",
    ]


def test_records_that_did_not_parse_are_said() -> None:
    (line,) = describe([Outcome("USGS", "recovered", recovered=5, present=1, skipped=2)], "en")

    assert line == "USGS      recovered 5 · already present 1 · unreadable 2"


def test_the_exit_code_says_whether_anything_could_be_recovered() -> None:
    ok = Outcome("EMSC", "recovered", recovered=0)
    failed = Outcome("USGS", "failed", detail="HTTP 500")
    never = Outcome("FUNVISIS", "not_recoverable", detail="no dates")

    assert exit_code([ok, failed, never]) == 0  # at least one network was read
    assert exit_code([failed, never]) == 1  # every recoverable network failed
    assert exit_code([never]) == 0  # nothing to recover is not a failure
