"""The summary of the period, on the history screen (REQ-EST-001, REQ-EST-003).

Split like the list and the playback: `describe` decides what is said -- the
sections, each line's wording, and beside every figure the number of entries
it was computed over and the period -- and needs no display; `StatsView` only
draws that, in Flet controls.

The bars are `Container`s whose width is proportional to the value (decision
D-6): no charting library, and so no new dependency. That is enough for bars;
lines or fine axes would be a new decision, not an extension of this one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import Any

import flet as ft

from vigia_eew.history_stats import NO_REASON, Latency, Period, Split, Summary
from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.notify.history_view import REASONS
from vigia_eew.notify.presentation import VENEZUELA_ZONE
from vigia_eew.timeutil import local_date

#: Width of the longest bar of a section, in logical pixels.
BAR_WIDTH = 220

_BAR_HEIGHT = 12
_LABEL_WIDTH = 210
_VALUE_WIDTH = 70


@dataclass(frozen=True, slots=True)
class Line:
    """One figure: what it is about, its value, and how long its bar is."""

    label: str
    value: str
    #: The bar, as a share of the section's longest; None when there is no
    #: figure to draw.
    fraction: float | None
    #: What this figure was computed over, when it differs from line to line
    #: (the latency). Otherwise the section says it once for all of them.
    basis: str | None = None


@dataclass(frozen=True, slots=True)
class Section:
    """One split, or the latencies: a heading, its basis and its lines."""

    title: str
    #: The entries and the period every line here was computed over, or None
    #: when each line carries its own.
    basis: str | None
    lines: tuple[Line, ...]


def format_delay(seconds: float) -> str:
    """A delay in the unit that fits it: seconds, minutes, hours or days."""
    size = abs(seconds)
    if size < 120:
        return f"{seconds:.0f} s"
    if size < 2 * 3600:
        return f"{seconds / 60:.0f} min"
    if size < 2 * 86400:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86400:.1f} d"


def _span(period: Period | None, zone: str) -> str:
    """A period as its first and last local day, or the one day it falls in."""
    if period is None:
        return ""
    first, last = (
        (local_date(moment, zone) or moment.astimezone(UTC).date()).isoformat() for moment in period
    )
    return first if first == last else f"{first} – {last}"


def _split_section(
    title_key: str, split: Split, locale_code: str, zone: str, label: Any = None
) -> Section:
    largest = max((bar.count for bar in split.bars), default=0)
    return Section(
        title=t(title_key, locale_code),
        basis=t(
            f"history_stats_over_{split.base}",
            locale_code,
            count=split.sample,
            period=_span(split.period, zone),
        ),
        lines=tuple(
            Line(
                label=label(bar.key) if label else bar.key,
                value=str(bar.count),
                fraction=bar.count / largest,
            )
            for bar in split.bars
        ),
    )


def _latency_section(figures: tuple[Latency, ...], locale_code: str, zone: str) -> Section:
    slowest = max((abs(f.median_s) for f in figures if f.median_s is not None), default=0.0)
    lines = []
    for figure in figures:
        if figure.median_s is None:
            # No live arrival is no figure -- and saying "0" would be a claim.
            lines.append(
                Line(
                    label=figure.source,
                    value=t("history_stats_no_figure", locale_code),
                    fraction=None,
                    basis=t("history_stats_no_live", locale_code),
                )
            )
            continue
        lines.append(
            Line(
                label=figure.source,
                value=format_delay(figure.median_s),
                fraction=abs(figure.median_s) / slowest if slowest else None,
                basis=t(
                    "history_stats_over_live",
                    locale_code,
                    count=figure.sample,
                    period=_span(figure.period, zone),
                ),
            )
        )
    return Section(title=t("history_stats_latency", locale_code), basis=None, lines=tuple(lines))


def describe(
    summary: Summary, *, locale_code: str = DEFAULT_LOCALE, zone: str = VENEZUELA_ZONE
) -> list[Section]:
    """What the summary says, section by section. Nothing at all for an empty set."""
    if summary.empty:
        return []

    def verdict(key: str) -> str:
        phrase_key = f"history_verdict_{key}"
        phrase = t(phrase_key, locale_code)
        return key if phrase == phrase_key else phrase

    def reason(key: str) -> str:
        if key == NO_REASON:
            return t("history_stats_no_reason", locale_code)
        phrase_key = REASONS.get(key)
        return t(phrase_key, locale_code) if phrase_key else key

    sections = [
        _split_section("history_stats_per_day", summary.per_day, locale_code, zone),
        _split_section("history_stats_by_magnitude", summary.by_magnitude, locale_code, zone),
        _split_section("history_stats_by_verdict", summary.by_verdict, locale_code, zone, verdict),
    ]
    if summary.by_reason.sample:
        sections.append(
            _split_section("history_stats_by_reason", summary.by_reason, locale_code, zone, reason)
        )
    sections.append(_split_section("history_stats_by_source", summary.by_source, locale_code, zone))
    sections.append(_latency_section(summary.latency, locale_code, zone))
    return sections


class StatsView:
    """Draws a summary. Decides nothing: `describe` already said what is shown."""

    def __init__(self, *, locale_code: str = DEFAULT_LOCALE, zone: str = VENEZUELA_ZONE) -> None:
        self._locale = locale_code
        self._zone = zone
        self.sections: list[Section] = []
        self.view = ft.ResponsiveRow(spacing=24, run_spacing=16, controls=[])

    def show(self, summary: Summary) -> None:
        """Replaces what is drawn with that summary."""
        self.sections = describe(summary, locale_code=self._locale, zone=self._zone)
        if not self.sections:
            # Said, not computed: no heading and no bar, so nothing reads as zero.
            self.view.controls = [
                ft.Container(
                    col=12, content=ft.Text(t("history_stats_empty", self._locale), italic=True)
                )
            ]
            return
        self.view.controls = [
            ft.Container(col={"xs": 12, "md": 6, "xl": 4}, content=self._draw(section))
            for section in self.sections
        ]

    def _draw(self, section: Section) -> Any:
        controls: list[Any] = [ft.Text(section.title, weight=ft.FontWeight.BOLD)]
        if section.basis:
            controls.append(ft.Text(section.basis, size=11, color=ft.Colors.ON_SURFACE_VARIANT))
        controls.extend(self._draw_line(line) for line in section.lines)
        return ft.Column(spacing=4, controls=controls)

    @staticmethod
    def _draw_line(line: Line) -> Any:
        row: list[Any] = [
            ft.Text(line.label, size=12, width=_LABEL_WIDTH, no_wrap=True),
            ft.Text(line.value, size=12, width=_VALUE_WIDTH, text_align=ft.TextAlign.RIGHT),
        ]
        if line.fraction is not None:
            row.append(
                ft.Container(
                    data="bar",
                    # Never thinner than a pixel: a category that is there
                    # should not look like one that is not.
                    width=max(1.0, BAR_WIDTH * line.fraction),
                    height=_BAR_HEIGHT,
                    border_radius=2,
                    bgcolor=ft.Colors.PRIMARY,
                )
            )
        drawn: Any = ft.Row(
            spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=row
        )
        if line.basis is None:
            return drawn
        return ft.Column(
            spacing=0,
            controls=[drawn, ft.Text(line.basis, size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
        )
