"""What the maps share: the tile provider, symbol sizes and the alert's viewport.

Two windows draw a map -- the alert (where did it happen, and how far is
that from me?) and the history (where have they been happening?). Both use
`flet-map`, which wraps Flutter's `flutter_map`: it downloads and caches the
OpenStreetMap tiles itself, so the agent no longer carries a tile client of
its own (ADR-030).

Split like every view in `notify/`: the functions at the top decide -- how
big a symbol is, where the camera goes, what the caption says -- and need no
display; the builders at the bottom turn those decisions into controls.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.presentation import AlertData

#: OpenStreetMap's standard tiles. The usage policy asks for an identifying
#: User-Agent, which `flutter_map` builds from the package name below.
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
ATTRIBUTION = "OpenStreetMap contributors"
USER_AGENT_PACKAGE = "io.github.ecrespo.vigia_eew"

#: Smallest and largest a symbol may get, in pixels. The floor keeps a
#: magnitude 1 visible and clickable; the ceiling stops a magnitude 8 from
#: covering the country it happened in.
MIN_RADIUS = 4
MAX_RADIUS = 22

#: Zoom when the alert has nothing to frame but the epicentre.
EPICENTRE_ZOOM = 7.0

#: Beyond this the reference point is left out of the frame: an earthquake on
#: the other side of an ocean is better read close up than as a dot on a
#: continent-wide view.
FRAME_BOTH_UP_TO_KM = 2500.0

#: Room around the two framed points: a fraction of their separation, and never
#: less than this many degrees (two points a few km apart would zoom to a street).
FRAME_MARGIN_RATIO = 0.25
FRAME_MARGIN_DEG = 0.3

#: The map's width the fit is computed for -- a conservative guess, since the
#: real width depends on the window. Narrower than the usual 600-1100 px so
#: the frame errs on showing more, never on cutting a point off.
FIT_VIEWPORT_PX = 520.0

#: How much taller than wide the map's frame is treated as, for the latitude span.
FIT_ASPECT = 1.4

#: Colours of the alert map's two symbols.
EPICENTRE_COLOR = "#D32F2F"
REFERENCE_COLOR = "#1565C0"


def marker_radius(magnitude: float) -> int:
    """How big a symbol is, from the magnitude it represents (REQ-MAP-003).

    Linear in magnitude rather than in released energy. Energy is the honest
    physical scale and it is useless here: a magnitude 7 releases about thirty
    thousand times what a 4 does, which on a screen is either a dot or a
    continent. What the criterion asks for is that the order be readable and
    a 6 be visibly bigger than a 3, and that is what this gives.
    """
    radius = MIN_RADIUS + max(0.0, magnitude) * 2.4
    return int(min(MAX_RADIUS, max(MIN_RADIUS, radius)))


@dataclass(frozen=True, slots=True)
class Camera:
    """Where the alert's map opens: a centre and a zoom level."""

    centre: tuple[float, float]
    zoom: float


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def zoom_to_fit(span_deg: float, *, viewport_px: float = FIT_VIEWPORT_PX) -> float:
    """The Web-Mercator zoom at which `span_deg` of longitude fills `viewport_px`.

    Computed here rather than left to the map control's camera fit: that fit
    is resolved against the control's size at first layout, which for a
    fullscreen alert is the size *before* the window grows -- and the
    epicentre ended up on the edge.
    """
    span = max(span_deg, 1e-6)
    zoom = math.log2(360.0 * viewport_px / (256.0 * span))
    return max(2.0, min(EPICENTRE_ZOOM + 2, zoom))


def alert_camera(data: AlertData) -> Camera:
    """Frames the epicentre, and the reference point too when it is close enough.

    Both points are framed with room to spare: the caption hangs above the
    pin, and a frame fitted to the bare points cuts it off at the edge.
    """
    epicentre = (data.latitude, data.longitude)
    reference = data.reference
    if reference is None or _distance_km(epicentre, reference) > FRAME_BOTH_UP_TO_KM:
        return Camera(centre=epicentre, zoom=EPICENTRE_ZOOM)
    lat_span = abs(epicentre[0] - reference[0])
    # A degree of latitude is wider on screen than one of longitude away from
    # the equator (Mercator), so the latitude span counts for more.
    stretch = 1 / max(0.2, math.cos(math.radians((epicentre[0] + reference[0]) / 2)))
    span = max(abs(epicentre[1] - reference[1]), lat_span * stretch * FIT_ASPECT)
    span = span * (1 + 2 * FRAME_MARGIN_RATIO) + 2 * FRAME_MARGIN_DEG
    centre = ((epicentre[0] + reference[0]) / 2, (epicentre[1] + reference[1]) / 2)
    return Camera(centre=centre, zoom=zoom_to_fit(span))


def epicentre_caption(data: AlertData, locale_code: str = DEFAULT_LOCALE) -> str:
    """The label next to the epicentre: where, the coordinates, and how strong."""
    return (
        f"{data.magnitude} · {data.place}\n"
        f"{t('coordinates_label', locale_code)}: {data.coordinates}"
    )


# --- Controls ----------------------------------------------------------------------


def _point(lat: float, lon: float) -> Any:
    import flet_map as fm

    return fm.MapLatitudeLongitude(lat, lon)


def tile_layer(on_error: Callable[[Any], None] | None = None) -> Any:
    """The OpenStreetMap layer; `on_error` hears about every tile that failed."""
    import flet_map as fm

    return fm.TileLayer(
        url_template=TILE_URL,
        user_agent_package_name=USER_AGENT_PACKAGE,
        on_image_error=on_error,
    )


def attribution_layer() -> Any:
    """The licence requires the attribution wherever a tile is (REQ-MAP-005)."""
    import flet_map as fm

    return fm.SimpleAttribution(text=ATTRIBUTION, bgcolor="#FFFFFFCC")  # adds the ©


def build_alert_map(data: AlertData, *, locale_code: str = DEFAULT_LOCALE) -> Any:
    """The alert's map: the epicentre with its caption, and the reference point.

    The epicentre is a circle sized by magnitude under a pin with a caption --
    the circle says how big, the pin says exactly where, and the caption says
    what the text panel says, so the map alone is enough to read the alert.
    """
    import flet as ft
    import flet_map as fm

    camera = alert_camera(data)
    epicentre = _point(data.latitude, data.longitude)
    circles = [
        fm.CircleMarker(
            coordinates=epicentre,
            radius=marker_radius(data.magnitude_value) * 2,
            color=ft.Colors.with_opacity(0.35, EPICENTRE_COLOR),
            border_color=EPICENTRE_COLOR,
            border_stroke_width=3,
        )
    ]
    markers = [
        fm.Marker(
            coordinates=epicentre,
            width=280,
            height=110,
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ft.Container(
                        content=ft.Text(
                            epicentre_caption(data, locale_code),
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color="#1B2028",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        bgcolor="#FFFFFFE6",
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    ),
                    ft.Icon(ft.Icons.LOCATION_ON, color=EPICENTRE_COLOR, size=40),
                ],
            ),
        )
    ]
    if data.reference is not None:
        markers.append(
            fm.Marker(
                coordinates=_point(*data.reference),
                width=160,
                height=56,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                    controls=[
                        ft.Icon(ft.Icons.MY_LOCATION, color=REFERENCE_COLOR, size=22),
                        ft.Text(
                            data.reference_name or t("your_location", locale_code),
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=REFERENCE_COLOR,
                        ),
                    ],
                ),
            )
        )
    return fm.Map(
        expand=True,
        initial_center=_point(*camera.centre),
        initial_zoom=camera.zoom,
        layers=[
            tile_layer(),
            fm.CircleLayer(circles=circles),
            fm.MarkerLayer(markers=markers),
            attribution_layer(),
        ],
    )
