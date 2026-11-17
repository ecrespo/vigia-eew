"""The history, written to a file of the user's (T-174, REQ-HIS-014, HU-118).

REQ-HIS-006 forbids the agent transmitting the history. It does not forbid the
user saving their own data to their own disk -- and the test that keeps the two
apart is the last one here: the module that exports imports nothing that could
send.
"""

from __future__ import annotations

import ast
import csv
import io
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from vigia_eew import history_export
from vigia_eew.history import EventRecord
from vigia_eew.history_export import COLUMNS, FORMATS, write, write_csv, write_geojson

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _record(event_id: str = "e1", **changes) -> EventRecord:
    values = {
        "correlation_id": f"tr-{event_id}",
        "source": "EMSC",
        "source_event_id": event_id,
        "occurred_at": _WHEN,
        "recorded_at": _WHEN + timedelta(minutes=5),
        "latitude": 10.6,
        "longitude": -66.9,
        "depth_km": 12.0,
        "magnitude": 4.5,
        "region": "NEAR THE COAST OF VENEZUELA",
        "distance_km": 20.0,
        "verdict": "discarded",
        "reason": "magnitude",
    }
    values.update(changes)
    return EventRecord(**values)


def _csv(records) -> list[list[str]]:
    out = io.StringIO()
    write_csv(records, out)
    return list(csv.reader(io.StringIO(out.getvalue())))


def _geojson(records) -> dict:
    out = io.StringIO()
    write_geojson(records, out)
    return json.loads(out.getvalue())


# --- CA-118.9 · The tabular file opens in a spreadsheet ------------------------------


def test_the_first_row_names_the_columns() -> None:
    rows = _csv([_record()])

    assert rows[0] == list(COLUMNS)
    assert {"occurred_at", "recorded_at", "magnitude", "latitude", "longitude"} <= set(rows[0])


def test_there_is_one_row_for_each_entry_after_the_header() -> None:
    rows = _csv([_record("a"), _record("b"), _record("c")])

    assert len(rows) == 1 + 3
    assert [row[rows[0].index("source_event_id")] for row in rows[1:]] == ["a", "b", "c"]


def test_every_instant_is_in_utc_with_its_offset() -> None:
    caracas = timezone(timedelta(hours=-4))
    local = _record(occurred_at=_WHEN.astimezone(caracas))

    rows = _csv([local])

    header, row = rows
    for column in ("occurred_at", "recorded_at"):
        moment = datetime.fromisoformat(row[header.index(column)])
        assert moment.utcoffset() == timedelta(0)
    assert row[header.index("occurred_at")] == "2026-09-19T12:00:00+00:00"


def test_what_the_history_does_not_know_is_an_empty_cell() -> None:
    header, row = _csv([_record(depth_km=None, region=None, reason=None)])

    for column in ("depth_km", "region", "reason"):
        assert row[header.index(column)] == ""


def test_a_place_with_a_comma_in_it_stays_one_cell() -> None:
    header, row = _csv([_record(region='10 km N of "El Tocuyo", Lara')])

    assert row[header.index("region")] == '10 km N of "El Tocuyo", Lara'
    assert len(row) == len(header)


@pytest.mark.parametrize("opening", ["=", "+", "-", "@", "\t", "\r"])
def test_text_a_spreadsheet_would_run_as_a_formula_is_written_as_text(opening: str) -> None:
    """The place and the ids come from the networks, not from the user.

    A cell that opens with one of these is a formula to a spreadsheet, and
    the file is made to be opened in one. A leading apostrophe makes it text.
    """
    hostile = opening + 'HYPERLINK("http://example.invalid","NEAR CARACAS")'

    header, row = _csv([_record(region=hostile, source_event_id=hostile)])

    assert row[header.index("region")] == "'" + hostile
    assert row[header.index("source_event_id")] == "'" + hostile


def test_a_negative_number_is_still_a_number() -> None:
    header, row = _csv([_record(longitude=-66.9, latitude=-10.5)])

    assert row[header.index("longitude")] == "-66.9"
    assert row[header.index("latitude")] == "-10.5"


def test_the_geographic_file_keeps_the_text_as_the_network_gave_it() -> None:
    """Nothing runs a GeoJSON property: there it is data, and is left alone."""
    properties = _geojson([_record(region="=SUM(A1)")])["features"][0]["properties"]

    assert properties["region"] == "=SUM(A1)"


def test_an_empty_set_is_a_header_and_nothing_else() -> None:
    assert _csv([]) == [list(COLUMNS)]


# --- CA-118.10 · The geographic file opens in a GIS ----------------------------------


def test_the_geographic_file_is_a_feature_collection() -> None:
    document = _geojson([_record("a"), _record("b")])

    assert document["type"] == "FeatureCollection"
    assert len(document["features"]) == 2
    assert all(feature["type"] == "Feature" for feature in document["features"])


def test_each_point_is_longitude_then_latitude() -> None:
    feature = _geojson([_record(latitude=10.6, longitude=-66.9)])["features"][0]

    assert feature["geometry"] == {"type": "Point", "coordinates": [-66.9, 10.6]}


def test_a_feature_carries_the_rest_of_the_entry() -> None:
    properties = _geojson([_record()])["features"][0]["properties"]

    assert properties["magnitude"] == 4.5
    assert properties["occurred_at"] == "2026-09-19T12:00:00+00:00"
    assert properties["verdict"] == "discarded"
    assert set(properties) == set(COLUMNS) - {"latitude", "longitude"}


def test_what_is_not_known_is_null_in_the_geographic_file() -> None:
    properties = _geojson([_record(depth_km=None)])["features"][0]["properties"]

    assert properties["depth_km"] is None


def test_an_empty_set_is_still_a_valid_collection() -> None:
    assert _geojson([]) == {"type": "FeatureCollection", "features": []}


# --- The formats on offer -------------------------------------------------------------


def test_two_open_formats_are_offered_each_with_its_extension() -> None:
    assert {key: fmt.extension for key, fmt in FORMATS.items()} == {
        "csv": ".csv",
        "geojson": ".geojson",
    }


def test_writing_by_format_name_is_writing_with_that_format() -> None:
    by_name, direct = io.StringIO(), io.StringIO()

    write([_record()], by_name, "geojson")
    write_geojson([_record()], direct)

    assert by_name.getvalue() == direct.getvalue()


def test_a_format_nobody_offers_is_refused() -> None:
    with pytest.raises(ValueError, match="csv"):
        write([_record()], io.StringIO(), "xlsx")


# --- CA-118.11 · Exporting opens no connection ----------------------------------------


def test_the_exporter_imports_no_network_library_and_no_toolkit() -> None:
    with open(history_export.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    outside = {name for name in imported if not name.startswith("vigia_eew")}
    # Everything it takes from outside the package, by name: the two writers
    # and the furniture of the language. Anything else has to be argued for.
    allowed = {"__future__", "csv", "json", "collections.abc", "dataclasses", "datetime", "typing"}
    assert outside <= allowed
    for forbidden in ("flet", "httpx", "websockets", "socket", "urllib", "http", "sqlite3"):
        assert not any(name == forbidden or name.startswith(forbidden + ".") for name in imported)
