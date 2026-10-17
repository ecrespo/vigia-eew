"""Tests for the views' window sizes and responsive breakpoints (T-151, ADR-030)."""

from __future__ import annotations

from vigia_eew.notify import ui_scale


def test_an_ordinary_screen_opens_above_its_floor():
    assert ui_scale.PREFERRED_SIZE[0] > ui_scale.MINIMUM_SIZE[0]
    assert ui_scale.PREFERRED_SIZE[1] > ui_scale.MINIMUM_SIZE[1]


def test_the_floor_is_narrow_enough_for_a_half_screen_window():
    """Responsive means it still works snapped to half of a 1366 px laptop."""
    assert ui_scale.MINIMUM_SIZE[0] <= 1366 // 2


def test_every_layout_is_a_single_column_on_a_phone_width():
    for columns in (
        ui_scale.FIELD_COLUMNS,
        ui_scale.ALERT_TEXT_COLUMNS,
        ui_scale.ALERT_MAP_COLUMNS,
        ui_scale.HISTORY_TABLE_COLUMNS,
        ui_scale.HISTORY_MAP_COLUMNS,
    ):
        assert columns["xs"] == 12


def test_side_by_side_layouts_add_up_to_one_row():
    wide = "md"
    assert ui_scale.ALERT_TEXT_COLUMNS[wide] + ui_scale.ALERT_MAP_COLUMNS[wide] == 12
    assert ui_scale.HISTORY_TABLE_COLUMNS["lg"] + ui_scale.HISTORY_MAP_COLUMNS["lg"] == 12


def test_no_span_exceeds_the_grid():
    for columns in (ui_scale.FIELD_COLUMNS, ui_scale.ALERT_MAP_COLUMNS):
        assert all(0 < span <= 12 for span in ui_scale.spans(columns))
