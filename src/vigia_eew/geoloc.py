"""IP-based location detection (RF-33) — best-effort, non-blocking at startup.

When the user doesn't configure `[reference]` in `config.toml`, `Application` falls
back to `detect_ip_location()` to estimate the geographic reference point by querying
a public HTTPS IP-geolocation service (`ipapi.co`, no API key). Any failure (network,
timeout, unexpected status, invalid JSON, or missing fields) is translated to `None`:
the caller falls back to the default (Caracas) without preventing the agent from
starting, the same fault-isolation principle used in `notify/toast.py`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from vigia_eew.config import ReferencePoint

IP_GEOLOCATION_URL = "https://ipapi.co/json/"
TIMEOUT_S = 5.0


def _parse_response(data: dict[str, Any]) -> ReferencePoint | None:
    """Translates `ipapi.co`'s JSON into a `ReferencePoint`. Pure, testable with fixtures."""
    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    name = data.get("city") or data.get("country_name") or "Detected location"
    try:
        return ReferencePoint(name=str(name), lat=lat, lon=lon)
    except ValueError:
        # Includes pydantic.ValidationError (a ValueError subclass): lat/lon out of range.
        return None


def detect_ip_location(
    *, client: httpx.Client | None = None, logger: logging.Logger | None = None
) -> ReferencePoint | None:
    """Attempts to detect the reference point by IP; `None` on failure (RF-33)."""
    log = logger or logging.getLogger("vigia_eew.geoloc")
    active_client = client or httpx.Client()
    try:
        try:
            resp = active_client.get(IP_GEOLOCATION_URL, timeout=TIMEOUT_S)
        except httpx.HTTPError as exc:
            log.warning("geoloc_network_error type=%s detail=%s", type(exc).__name__, exc)
            return None

        if resp.status_code != 200:
            log.warning("geoloc_unexpected_status status=%d", resp.status_code)
            return None

        try:
            data = resp.json()
        except ValueError as exc:
            log.warning("geoloc_invalid_json detail=%s", exc)
            return None

        reference = _parse_response(data)
        if reference is None:
            log.warning("geoloc_incomplete_response")
        return reference
    finally:
        if client is None:
            active_client.close()
