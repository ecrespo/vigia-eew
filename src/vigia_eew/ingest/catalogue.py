"""Reading a **period** from a network's catalogue (REQ-HIS-010, ADR-036).

The live pollers ask a catalogue *"what is new since my cursor?"*, and what
they read can open a window. This module asks the same FDSN service a
different question -- *"what happened between these two dates?"* -- for the
one purpose of completing the history, and it does nothing but read: it
yields raw payloads, in the dialect each network's own translation already
understands, and knows nothing of queues, cursors, the state or the history
([[lat.md/history#Recovery is a separate path that writes only to the history]]).

It asks in windows of thirty days and pages through each, so that no request
depends on what a server is willing to return at once. One window at a time
per network: nobody is helped by parallel requests to one host.

A source that cannot be read this way says so, with the reason
(`NotRecoverable`), instead of being absent. FUNVISIS publishes its twenty
most recent earthquakes and takes no dates; a history completed from the
other three is missing the small local ones, and the outcome has to say it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx

from vigia_eew.config import Settings
from vigia_eew.ingest import RawMessage
from vigia_eew.models import Source

#: The longest stretch asked for in one request, and how many events a page
#: holds. A year is thirteen requests per network, plus the pages.
WINDOW_DAYS = 30
PAGE = 1000

#: Seconds a request may take, and how long to wait before its one retry.
TIMEOUT_S = 30.0
RETRY_AFTER_S = 2.0

#: FDSN expresses a search radius in degrees. Degrees for all three networks,
#: so that there is one conversion.
KM_PER_DEGREE = 111.195

#: Who is asking. A name and nothing else: no address, no machine, no user.
USER_AGENT = "vigia-eew (catalogue recovery)"

_Sleep = Callable[[float], Awaitable[Any]]


class CatalogueError(RuntimeError):
    """A network's catalogue could not be read. The message is for the outcome."""


@dataclass(frozen=True, slots=True)
class Catalogue:
    """How to read one source's catalogue.

    Attributes:
        url_of: where it is, from the configuration.
        format: the value of FDSN's `format` parameter.
        parse: turns a response into raw payloads, one per event.
        extra: parameters only this service takes.
        keep: whether a payload is an earthquake at all.
    """

    url_of: Callable[[Settings], str]
    format: str
    parse: Callable[[Any], list[dict[str, Any]]]
    extra: dict[str, str] = field(default_factory=dict)
    keep: Callable[[dict[str, Any]], bool] = lambda _payload: True


@dataclass(frozen=True, slots=True)
class NotRecoverable:
    """Why a source's past cannot be read, in a sentence and as a text key."""

    reason: str
    reason_key: str


def features_of(response: Any) -> list[dict[str, Any]]:
    """The features of a GeoJSON `FeatureCollection` (EMSC, USGS)."""
    features = response.json()["features"]
    if not isinstance(features, list):
        raise ValueError("the catalogue's features are not a list")
    return [feature for feature in features if isinstance(feature, dict)]


def windows(since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
    """The period cut into stretches of at most `WINDOW_DAYS`, oldest first."""
    spans = []
    start = since
    while start < until:
        end = min(until, start + timedelta(days=WINDOW_DAYS))
        spans.append((start, end))
        start = end
    return spans


async def fetch(
    source: Source,
    catalogue: Catalogue,
    cfg: Settings,
    since: datetime,
    until: datetime,
    *,
    client: Any,
    sleep: _Sleep = asyncio.sleep,
    logger: logging.Logger | None = None,
) -> AsyncIterator[RawMessage]:
    """Yields every event of that source's catalogue in the period.

    The circle asked for is the recovery's own -- `[history]
    recovery_radius_km` around the reference point, from
    `recovery_min_magnitude` up -- not the alert's.

    Raises `CatalogueError` when the service cannot be read; what was yielded
    before that has been read and stays valid.
    """
    log = logger or logging.getLogger("vigia_eew.ingest.catalogue")
    url = catalogue.url_of(cfg)
    for start, end in windows(since, until):
        offset = 1  # FDSN counts from one
        while True:
            params = _params(catalogue, cfg, start, end, offset)
            payloads = await _page(source, catalogue, url, params, client, sleep, log)
            for payload in filter(catalogue.keep, payloads):
                yield RawMessage(source=source, action="create", feature=payload)
            if len(payloads) < PAGE:
                break  # a short page is the last one of its window
            offset += PAGE


def _params(
    catalogue: Catalogue, cfg: Settings, start: datetime, end: datetime, offset: int
) -> dict[str, Any]:
    """The FDSN query for one page of one window (03 §3.1)."""
    return {
        "format": catalogue.format,
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "latitude": cfg.reference.lat,
        "longitude": cfg.reference.lon,
        "maxradius": cfg.history.recovery_radius_km / KM_PER_DEGREE,
        "minmagnitude": cfg.history.recovery_min_magnitude,
        "orderby": "time",
        "limit": PAGE,
        "offset": offset,
        **catalogue.extra,
    }


async def _page(
    source: str,
    catalogue: Catalogue,
    url: str,
    params: dict[str, Any],
    client: Any,
    sleep: _Sleep,
    log: logging.Logger,
) -> list[dict[str, Any]]:
    """One request, with its one retry, as raw payloads."""
    response = await _get(source, url, params, client, sleep, log)
    if response.status_code == 204:
        return []  # nothing in that window: an answer, not an error
    if response.status_code != 200:
        first_line = (str(response.text or "").strip().splitlines() or [""])[0]
        detail = f": {first_line}" if first_line else ""
        raise CatalogueError(f"HTTP {response.status_code}{detail}")
    try:
        return catalogue.parse(response)
    except (ValueError, KeyError, TypeError) as exc:
        raise CatalogueError(f"unreadable answer ({type(exc).__name__}: {exc})") from exc


async def _get(
    source: str, url: str, params: dict[str, Any], client: Any, sleep: _Sleep, log: logging.Logger
) -> Any:
    """The response, retrying once what may be a passing outage.

    A timeout, a 429 and a 5xx are retried: the service may be back in two
    seconds. A 400 is not -- the same request would be refused again.
    """
    failure = ""
    for attempt in (1, 2):
        try:
            response = await client.get(
                url, params=params, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}
            )
        except httpx.TimeoutException:
            failure = f"timeout after {TIMEOUT_S:.0f} s"
        except httpx.HTTPError as exc:
            failure = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code != 429 and response.status_code < 500:
                return response
            failure = f"HTTP {response.status_code}"
        log.warning(
            "catalogue_unavailable source=%s attempt=%d detail=%s", source, attempt, failure
        )
        if attempt == 1:
            await sleep(RETRY_AFTER_S)
    raise CatalogueError(failure)
