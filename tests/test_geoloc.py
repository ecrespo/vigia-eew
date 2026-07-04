"""Tests for IP-based location detection (RF-33)."""

from __future__ import annotations

import httpx

from vigia_eew.geoloc import detect_ip_location


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, *, invalid_json=False):
        self.status_code = status_code
        self._payload = payload or {}
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("not json")
        return self._payload


class _FakeClient:
    def __init__(self, response=None, *, exception=None):
        self._response = response
        self._exception = exception
        self.closed = False

    def get(self, url, *, timeout=None):
        if self._exception is not None:
            raise self._exception
        return self._response

    def close(self):
        self.closed = True


def test_successful_detection():
    client = _FakeClient(
        _FakeResponse(200, {"city": "Caracas", "latitude": 10.5, "longitude": -66.9})
    )
    ref = detect_ip_location(client=client)
    assert ref is not None
    assert ref.name == "Caracas"
    assert ref.lat == 10.5
    assert ref.lon == -66.9


def test_network_error_returns_none():
    client = _FakeClient(exception=httpx.ConnectError("no network"))
    assert detect_ip_location(client=client) is None


def test_non_200_status_returns_none():
    client = _FakeClient(_FakeResponse(503))
    assert detect_ip_location(client=client) is None


def test_invalid_json_returns_none():
    client = _FakeClient(_FakeResponse(200, invalid_json=True))
    assert detect_ip_location(client=client) is None


def test_missing_fields_returns_none():
    client = _FakeClient(_FakeResponse(200, {"city": "Caracas"}))  # no lat/lon
    assert detect_ip_location(client=client) is None


def test_lat_lon_out_of_range_returns_none():
    client = _FakeClient(_FakeResponse(200, {"latitude": 999.0, "longitude": -66.9}))
    assert detect_ip_location(client=client) is None


def test_without_city_uses_generic_name():
    client = _FakeClient(_FakeResponse(200, {"latitude": 1.0, "longitude": 2.0}))
    ref = detect_ip_location(client=client)
    assert ref is not None
    assert ref.name


def test_injected_client_is_not_closed():
    client = _FakeClient(_FakeResponse(200, {"latitude": 1.0, "longitude": 2.0}))
    detect_ip_location(client=client)
    assert client.closed is False
