"""The history, written out in two open formats (REQ-HIS-014, ADR-038).

*"The history does not leave the machine"* (REQ-HIS-006) forbids **the agent
transmitting it**. It does not forbid the user saving their own data to their
own disk, to open it in a spreadsheet or in a GIS. That reading is written
down rather than assumed ([[lat.md/history#It does not leave the machine]]),
and this module is what keeps it honest: it writes records to a file somebody
else opened, and it imports `csv`, `json` and nothing that could send. A test
on its imports says so.

Pure: it does not choose the destination, open it or decide what is exported.
The caller hands over the records of the reading on screen -- the whole
filtered set, not the visible page -- and an open text file.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TextIO

from vigia_eew.history import EventRecord

#: What is written about each entry, in this order. The names are the stored
#: columns', so a file exported today and the schema describe the same thing.
COLUMNS = (
    "occurred_at",
    "recorded_at",
    "magnitude",
    "latitude",
    "longitude",
    "depth_km",
    "distance_km",
    "region",
    "source",
    "source_event_id",
    "verdict",
    "reason",
    "severity",
    "correlation_id",
)

_INSTANTS = ("occurred_at", "recorded_at")
_COORDINATES = ("latitude", "longitude")


def _values(record: EventRecord) -> dict[str, Any]:
    """One entry by column. Instants as ISO-8601 in UTC with the offset (Art. 4)."""
    values: dict[str, Any] = {column: getattr(record, column) for column in COLUMNS}
    for column in _INSTANTS:
        moment: datetime = values[column]
        values[column] = moment.astimezone(UTC).isoformat()
    return values


def write_csv(records: Iterable[EventRecord], out: TextIO) -> None:
    """Writes those entries as CSV: a header naming the columns, then a row each.

    What is not known is an empty cell. `out` should have been opened with
    `newline=""`, as the `csv` module asks, so a row ends once on every system.
    """
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for record in records:
        values = _values(record)
        writer.writerow(["" if values[column] is None else values[column] for column in COLUMNS])


def write_geojson(records: Iterable[EventRecord], out: TextIO) -> None:
    """Writes those entries as a GeoJSON `FeatureCollection` of points.

    A position is `[longitude, latitude]`, in that order: it is what the
    format says, and the opposite of how everybody says it aloud.
    """
    features = []
    for record in records:
        values = _values(record)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [record.longitude, record.latitude],
                },
                "properties": {
                    column: values[column] for column in COLUMNS if column not in _COORDINATES
                },
            }
        )
    json.dump({"type": "FeatureCollection", "features": features}, out, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class Format:
    """One format on offer: the extension of its files, and what writes them."""

    extension: str
    writer: Callable[[Iterable[EventRecord], TextIO], None]


#: The formats the export offers, by the name the screen chooses them with:
#: one tabular and one geographic, both open (REQ-HIS-014).
FORMATS: dict[str, Format] = {
    "csv": Format(".csv", write_csv),
    "geojson": Format(".geojson", write_geojson),
}


def write(records: Iterable[EventRecord], out: TextIO, format_name: str) -> None:
    """Writes those entries in the format of that name, or refuses the name."""
    try:
        chosen = FORMATS[format_name]
    except KeyError:
        raise ValueError(
            f"cannot export as {format_name!r}; the formats are {', '.join(FORMATS)}"
        ) from None
    chosen.writer(records, out)
