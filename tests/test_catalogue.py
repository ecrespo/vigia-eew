"""Tests for reading a period from a network's catalogue (T-169, REQ-HIS-010, ADR-036).

The live pollers ask a catalogue "what is new since my cursor?". The recovery
asks the same service a different question -- "what happened between these two
dates?" -- and that question has its own failure modes: a period longer than a
server will answer in one go, a page that is not the last, a network that is
down while the other two are not.

The client and the sleep are injected. One test, opt-in, reads a day from each
live service.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from vigia_eew.config import Settings
from vigia_eew.ingest import catalogue
from vigia_eew.ingest.catalogue import (
    PAGE,
    WINDOW_DAYS,
    Catalogue,
    CatalogueError,
    NotRecoverable,
    fetch,
    windows,
)
from vigia_eew.ingest.registry import SOURCE_REGISTRY, spec_for

_UNTIL = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

_GEOFON_HEADER = (
    "#EventID|Time|Latitude|Longitude|Depth/km|Author|Catalog|Contributor|ContributorID|"
    "MagType|Magnitude|MagAuthor|EventLocationName|EventType"
)


def _usgs_feature(index: int) -> dict:
    return {
        "id": f"us{index}",
        "properties": {"mag": 4.5, "magType": "mb", "time": 1_780_000_000_000 + index},
        "geometry": {"coordinates": [-66.9, 10.5, 10.0]},
    }


class _Resp:
    def __init__(self, status: int = 200, *, features=None, text: str = "", bad_json=False):
        self.status_code = status
        self._features = features
        self.text = text
        self._bad_json = bad_json
        self.headers: dict[str, str] = {}

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return {"type": "FeatureCollection", "features": self._features or []}


class _Client:
    """Answers each request from a queue; the last answer repeats."""

    def __init__(self, *answers) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, *, params=None, timeout=None, headers=None):
        self.calls.append((url, dict(params or {})))
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


async def _no_sleep(_seconds: float) -> None:
    return None


async def _read(source: str, client, *, days: float = 1, cfg: Settings | None = None) -> list:
    spec = spec_for(source)
    return [
        message
        async for message in fetch(
            spec.source,
            spec.recovery,
            cfg or Settings(),
            _UNTIL - timedelta(days=days),
            _UNTIL,
            client=client,
            sleep=_no_sleep,
        )
    ]


# --- Windows ------------------------------------------------------------------------


def test_a_period_is_asked_for_in_windows_of_thirty_days() -> None:
    spans = windows(_UNTIL - timedelta(days=65), _UNTIL)

    assert len(spans) == 3
    assert spans[0][0] == _UNTIL - timedelta(days=65)
    assert spans[-1][1] == _UNTIL
    assert all(end - start <= timedelta(days=WINDOW_DAYS) for start, end in spans)
    assert all(spans[i][1] == spans[i + 1][0] for i in range(2))  # no gap, no overlap


def test_a_period_shorter_than_a_window_is_one_request() -> None:
    assert windows(_UNTIL - timedelta(days=7), _UNTIL) == [(_UNTIL - timedelta(days=7), _UNTIL)]


def test_a_period_of_nothing_asks_for_nothing() -> None:
    assert windows(_UNTIL, _UNTIL) == []


# --- The request (03 §3.1) ------------------------------------------------------------


@pytest.mark.asyncio
async def test_sixty_five_days_make_three_requests_per_network() -> None:
    """CA-117.1: three windows, each short enough to be its own last page."""
    for source in ("EMSC", "USGS", "GEOFON"):
        client = _Client(_Resp(204))

        await _read(source, client, days=65)

        assert len(client.calls) == 3, source


@pytest.mark.asyncio
async def test_the_request_asks_for_the_recovery_s_circle_not_the_alert_s() -> None:
    cfg = Settings()
    client = _Client(_Resp(204))

    await _read("USGS", client, cfg=cfg)

    url, params = client.calls[0]
    assert url == cfg.sources_usgs.url
    assert params["format"] == "geojson"
    assert params["latitude"] == cfg.reference.lat
    assert params["longitude"] == cfg.reference.lon
    assert params["maxradius"] == pytest.approx(cfg.history.recovery_radius_km / 111.195)
    assert params["minmagnitude"] == cfg.history.recovery_min_magnitude
    assert params["starttime"] == "2026-11-15T12:00:00"
    assert params["endtime"] == "2026-11-16T12:00:00"
    assert (params["orderby"], params["limit"], params["offset"]) == ("time", PAGE, 1)
    assert params["eventtype"] == "earthquake"


@pytest.mark.asyncio
async def test_each_network_is_asked_at_its_own_url_in_its_own_format() -> None:
    cfg = Settings()
    asked = {}
    for source in ("EMSC", "USGS", "GEOFON"):
        client = _Client(_Resp(204))
        await _read(source, client, cfg=cfg)
        asked[source] = (client.calls[0][0], client.calls[0][1]["format"])

    assert asked == {
        "EMSC": (cfg.sources_emsc.catalog_url, "json"),
        "USGS": (cfg.sources_usgs.url, "geojson"),
        "GEOFON": (cfg.sources_geofon.url, "text"),
    }
    assert "eventtype" not in client.calls[0][1]  # GEOFON: USGS's parameter is USGS's


# --- Paging ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_full_page_is_followed_by_the_next_until_a_short_one() -> None:
    full = [_usgs_feature(i) for i in range(PAGE)]
    client = _Client(_Resp(features=full), _Resp(features=full), _Resp(features=full[:7]))

    messages = await _read("USGS", client)

    assert len(messages) == 2 * PAGE + 7
    assert [params["offset"] for _url, params in client.calls] == [1, 1 + PAGE, 1 + 2 * PAGE]


@pytest.mark.asyncio
async def test_what_is_read_is_in_the_dialect_the_normaliser_already_reads() -> None:
    """The recovery adds no second translation: the registry's own reads these."""
    client = _Client(_Resp(features=[_usgs_feature(1)]))

    (message,) = await _read("USGS", client)

    assert (message.source, message.action) == ("USGS", "create")
    assert spec_for("USGS").to_fields(message)["id"] == "us1"


@pytest.mark.asyncio
async def test_geofon_s_text_is_read_as_rows_and_blasts_are_left_out() -> None:
    body = "\n".join(
        [
            _GEOFON_HEADER,
            "gfz1|2026-11-16T01:00:00|10.5|-66.9|10.0|GFZ|||gfz1|mb|4.6|GFZ|Venezuela|earthquake",
            "gfz2|2026-11-16T02:00:00|10.5|-66.9|0.0|GFZ|||gfz2|ml|2.6|GFZ|Venezuela|quarry blast",
        ]
    )
    client = _Client(_Resp(text=body))

    (message,) = await _read("GEOFON", client)

    assert spec_for("GEOFON").to_fields(message)["id"] == "gfz1"


@pytest.mark.asyncio
async def test_emsc_s_catalogue_carries_the_properties_of_its_websocket() -> None:
    feature = {
        "id": "20261116_0000001",
        "properties": {
            "unid": "20261116_0000001",
            "time": "2026-11-16T01:00:00.0Z",
            "lat": 10.5,
            "lon": -66.9,
            "depth": 39.6,
            "mag": 4.4,
            "magtype": "mb",
            "flynn_region": "NEAR COAST OF VENEZUELA",
            "lastupdate": "2026-11-16T01:30:00.0Z",
        },
        "geometry": {"coordinates": [-66.9, 10.5, -39.6]},  # the depth is negative here
    }
    client = _Client(_Resp(features=[feature]))

    (message,) = await _read("EMSC", client)
    fields = spec_for("EMSC").to_fields(message)

    assert (fields["id"], fields["depth_km"]) == ("20261116_0000001", 39.6)


# --- Responses (03 §3.3) ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_content_is_an_empty_window_not_a_failure() -> None:
    assert await _read("EMSC", _Client(_Resp(204))) == []
    assert await _read("USGS", _Client(_Resp(features=[]))) == []


@pytest.mark.asyncio
async def test_a_server_error_is_retried_once_and_then_succeeds() -> None:
    client = _Client(_Resp(500), _Resp(features=[_usgs_feature(1)]))

    messages = await _read("USGS", client)

    assert len(messages) == 1
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_a_server_error_twice_is_reported() -> None:
    client = _Client(_Resp(500))

    with pytest.raises(CatalogueError, match="500"):
        await _read("USGS", client)

    assert len(client.calls) == 2  # the request and its one retry


@pytest.mark.asyncio
async def test_a_timeout_twice_is_reported_as_a_timeout() -> None:
    client = _Client(httpx.ReadTimeout("slow"))

    with pytest.raises(CatalogueError, match="timeout"):
        await _read("GEOFON", client)

    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_too_many_requests_is_retried_like_an_outage() -> None:
    client = _Client(_Resp(429), _Resp(204))

    assert await _read("EMSC", client) == []
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_a_refused_request_is_not_retried_and_says_why() -> None:
    client = _Client(_Resp(400, text="Error 400: Bad Request\nmaxradius out of range\n"))

    with pytest.raises(CatalogueError, match="Error 400: Bad Request"):
        await _read("USGS", client)

    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_a_body_that_is_not_what_was_asked_for_is_reported() -> None:
    with pytest.raises(CatalogueError):
        await _read("USGS", _Client(_Resp(bad_json=True)))


# --- The registry declares who can be recovered (ADR-036 §2) --------------------------


def test_three_networks_declare_a_catalogue_and_funvisis_declares_why_not() -> None:
    declared = {spec.source: spec.recovery for spec in SOURCE_REGISTRY}

    assert all(isinstance(declared[name], Catalogue) for name in ("EMSC", "USGS", "GEOFON"))
    assert isinstance(declared["FUNVISIS"], NotRecoverable)
    assert "date" in declared["FUNVISIS"].reason


def test_the_module_reads_and_nothing_else() -> None:
    """ADR-036: it yields payloads. Queues, cursors and the state are not its business."""
    import ast

    with open(catalogue.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any(name.startswith("vigia_eew.state") for name in imported)
    assert not any(name.startswith("vigia_eew.history") for name in imported)


# --- The live services (opt-in) -------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("VIGIA_NETWORK_TESTS") != "1",
    reason="reads the live catalogues; set VIGIA_NETWORK_TESTS=1",
)
async def test_a_day_is_read_from_each_live_catalogue() -> None:
    """Each service answers the request as this module writes it, and the
    registry's own translation reads what comes back."""
    cfg = Settings()
    until = datetime.now(UTC) - timedelta(days=2)
    async with httpx.AsyncClient() as client:
        for source in ("EMSC", "USGS", "GEOFON"):
            spec = spec_for(source)
            messages = [
                message
                async for message in fetch(
                    spec.source,
                    spec.recovery,
                    cfg,
                    until - timedelta(days=7),
                    until,
                    client=client,
                )
            ]
            for message in messages:
                assert spec.to_fields(message)["source"] == source
            print(f"{source}: {len(messages)} in a week")
