"""Tests for the configuration panel (T-136, REQ-GUI-001..004, HU-108).

The panel is **generated from the schema** (ADR-020). 39 fields written out
control by control is 39 chances for a field added to the model never to reach
the interface, and nobody finds out until a user cannot find the option.

So the split here is deliberate: everything that decides -- which controls
exist, what a value means, whether it validates, what gets written -- is pure
and tested headless. Only the widget tree needs a display, and that part has
its own opt-in smoke at the end.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from vigia_eew.config import Settings, bundled_example, load_config
from vigia_eew.config_writer import ConfigWriter, ExternalEdit, InvalidConfig
from vigia_eew.notify.config_panel import (
    CHOICES,
    PanelModel,
    UnsupportedField,
    describe,
)


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    return path


@pytest.fixture
def panel(config_file: Path) -> PanelModel:
    return PanelModel(ConfigWriter(config_file))


def _leaf_paths() -> set[str]:
    """Every leaf field of the configuration schema, by its dotted TOML path."""
    from vigia_eew.config import SECTION_PATHS

    paths = set()
    for field, toml_path in SECTION_PATHS.items():
        model = Settings.model_fields[field].annotation
        assert isinstance(model, type) and issubclass(model, BaseModel)
        for name in model.model_fields:
            paths.add(".".join((*toml_path, name)))
    return paths


# --- CA-108.1 · Every field of the schema has a control -------------------------


def test_every_field_in_the_schema_reaches_the_panel() -> None:
    """The check that makes the generation worth having."""
    described = {field.path for section in describe() for field in section.fields}
    assert described == _leaf_paths()


def test_the_ten_sections_are_all_present() -> None:
    sections = describe()
    assert len(sections) == 10
    assert [s.key for s in sections][:2] == ["reference", "filter"]


def test_a_field_the_generator_cannot_render_fails_by_name() -> None:
    """CA-108.2: an unhandled field stops the panel instead of vanishing from it.

    The generation covers the ordinary types. What it must never do is skip
    what it does not understand -- that is exactly the silent drift the
    schema-driven panel exists to prevent.
    """

    class Exotic(BaseModel):
        radius_km: float = 1.0
        shape: tuple[int, ...] = ()

    class Odd(BaseModel):
        exotic: Exotic = Field(default_factory=Exotic)

    with pytest.raises(UnsupportedField, match="shape"):
        describe(Odd, {"exotic": ("exotic",)})


def test_the_closed_domains_are_declared_rather_than_guessed() -> None:
    """ADR-020's honest cost: a few fields carry a control declared by hand."""
    assert "notification.language" in CHOICES
    assert CHOICES["notification.language"] == ("auto", "en", "es")
    assert "INFO" in CHOICES["logging.level"]
    choice_fields = {f.path for s in describe() for f in s.fields if f.kind == "choice"}
    assert choice_fields == set(CHOICES)


def test_a_field_carries_the_bounds_the_schema_declares() -> None:
    """The validation is the schema's, not a second copy written for the panel."""
    radius = next(f for s in describe() for f in s.fields if f.path == "filter.radius_km")
    assert radius.kind == "float"
    assert radius.default == 300.0
    assert radius.exclusive_minimum == 0


# --- The values the panel starts with -------------------------------------------


def test_it_opens_on_what_the_file_says(panel: PanelModel) -> None:
    assert panel.value("filter.radius_km") == 300.0
    assert panel.value("notification.language") == "auto"


def test_a_field_the_file_omits_shows_its_default(panel: PanelModel) -> None:
    """`[reference]` ships commented out, and the panel still has to show something."""
    assert panel.value("reference.name") == "Caracas"
    assert panel.declared("reference.name") is False


def test_a_file_that_does_not_exist_yet_opens_on_the_defaults(tmp_path: Path) -> None:
    empty = PanelModel(ConfigWriter(tmp_path / "config.toml"))
    assert empty.value("filter.min_magnitude") == 2.5


# --- CA-108.3 · Errors appear next to the field, before saving -------------------


def test_a_negative_radius_is_flagged_on_its_own_field(panel: PanelModel) -> None:
    panel.edit("filter.radius_km", "-1")

    assert "filter.radius_km" in panel.errors
    assert panel.can_save is False


def test_a_value_that_is_not_a_number_is_flagged_too(panel: PanelModel) -> None:
    panel.edit("filter.radius_km", "three hundred")

    assert "number" in panel.errors["filter.radius_km"].lower()
    assert panel.can_save is False


def test_correcting_the_value_clears_the_error(panel: PanelModel) -> None:
    panel.edit("filter.radius_km", "-1")
    panel.edit("filter.radius_km", "150")

    assert panel.errors == {}
    assert panel.can_save is True


def test_an_untouched_panel_can_be_saved(panel: PanelModel) -> None:
    assert panel.can_save is True


# --- CA-108.4 · A rule between two fields is validated as well --------------------


def test_the_severity_rule_is_reported_against_the_section(panel: PanelModel) -> None:
    """Neither field is wrong on its own; what is wrong is the pair."""
    panel.edit("severity.info_max", "6.0")

    assert "severity" in panel.errors
    assert "warning_max" in panel.errors["severity"]
    assert panel.can_save is False


def test_the_section_error_clears_when_the_pair_makes_sense_again(panel: PanelModel) -> None:
    panel.edit("severity.info_max", "6.0")
    panel.edit("severity.warning_max", "7.0")

    assert panel.errors == {}


# --- CA-108.9 / REQ-GUI-003 · Defaults, and what actually gets written ------------


def test_only_the_fields_the_user_changed_are_written(panel: PanelModel) -> None:
    """The panel must not write `[reference]` just because it displayed it.

    Its absence is what keeps the IP location detection alive (RF-33), so a
    panel that saved every field it showed would disable that the first time
    anybody pressed Save.
    """
    panel.edit("filter.radius_km", "150")

    assert panel.changes() == {"filter.radius_km": 150.0}


def test_setting_a_field_back_to_what_it_was_is_not_a_change(panel: PanelModel) -> None:
    panel.edit("filter.radius_km", "150")
    panel.edit("filter.radius_km", "300")

    assert panel.changes() == {}


def test_restoring_a_section_proposes_its_defaults_without_applying_them(
    panel: PanelModel, config_file: Path
) -> None:
    before = config_file.read_text(encoding="utf-8")
    panel.edit("filter.radius_km", "150")

    panel.restore_defaults("filter")

    assert panel.value("filter.radius_km") == 300.0
    assert config_file.read_text(encoding="utf-8") == before


def test_restoring_everything_covers_every_section(panel: PanelModel) -> None:
    panel.edit("filter.radius_km", "150")
    panel.edit("logging.level", "DEBUG")

    panel.restore_defaults()

    assert panel.value("filter.radius_km") == 300.0
    assert panel.value("logging.level") == "INFO"


def test_restoring_defaults_writes_back_what_the_file_had_overridden(
    config_file: Path,
) -> None:
    """A default restored over a value the file declares is a real change."""
    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace("radius_km = 300.0", "radius_km = 900.0"),
        encoding="utf-8",
    )
    panel = PanelModel(ConfigWriter(config_file))

    panel.restore_defaults("filter")

    assert panel.changes() == {"filter.radius_km": 300.0}


# --- Saving ----------------------------------------------------------------------


def test_saving_writes_through_the_writer(panel: PanelModel, config_file: Path) -> None:
    panel.edit("filter.radius_km", "150")

    panel.save()

    assert load_config(config_file).filter.radius_km == 150.0


def test_saving_says_the_agent_has_to_be_restarted(panel: PanelModel) -> None:
    """CA-108.9: the configuration is read once, at startup. Anything else is a lie."""
    panel.edit("filter.radius_km", "150")

    outcome = panel.save()

    assert outcome.restart_required is True


def test_after_saving_there_is_nothing_left_to_write(panel: PanelModel) -> None:
    panel.edit("filter.radius_km", "150")
    panel.save()

    assert panel.changes() == {}
    assert panel.value("filter.radius_km") == 150.0


def test_saving_an_invalid_panel_is_refused_before_the_writer(
    panel: PanelModel, config_file: Path
) -> None:
    before = config_file.read_text(encoding="utf-8")
    panel.edit("severity.info_max", "6.0")

    with pytest.raises(InvalidConfig):
        panel.save()

    assert config_file.read_text(encoding="utf-8") == before


def test_an_external_edit_reaches_the_panel_as_a_conflict(
    panel: PanelModel, config_file: Path
) -> None:
    """CA-108.7 end to end: the panel does not quietly win the race."""
    panel.edit("filter.radius_km", "150")
    edited = config_file.read_text(encoding="utf-8").replace(
        "min_magnitude = 2.5", "min_magnitude = 4.0"
    )
    config_file.write_text(edited, encoding="utf-8")
    os.utime(config_file, ns=(0, 0))

    with pytest.raises(ExternalEdit):
        panel.save()


def test_reloading_after_a_conflict_keeps_the_panel_usable(
    panel: PanelModel, config_file: Path
) -> None:
    """The way out has to exist, or the conflict is just a wall."""
    edited = config_file.read_text(encoding="utf-8").replace(
        "min_magnitude = 2.5", "min_magnitude = 4.0"
    )
    config_file.write_text(edited, encoding="utf-8")
    os.utime(config_file, ns=(0, 0))

    panel.reload()

    assert panel.value("filter.min_magnitude") == 4.0
    panel.edit("filter.radius_km", "150")
    panel.save()
    assert load_config(config_file).filter.radius_km == 150.0


# --- The widget tree (opt-in: VIGIA_GUI_TESTS=1) ----------------------------------


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_the_real_panel_builds_a_control_for_every_field(tmp_path: Path) -> None:
    import tkinter as tk

    from vigia_eew.notify.config_panel import ConfigPanel

    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    root = tk.Tk()
    panel = ConfigPanel(root, PanelModel(ConfigWriter(path)))
    root.update_idletasks()

    assert set(panel.controls) == _leaf_paths()
    root.destroy()


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_a_bad_value_disables_the_real_save_button(tmp_path: Path) -> None:
    import tkinter as tk

    from vigia_eew.notify.config_panel import ConfigPanel

    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    root = tk.Tk()
    panel = ConfigPanel(root, PanelModel(ConfigWriter(path)))
    root.update_idletasks()

    panel.controls["filter.radius_km"].set("-1")
    root.update_idletasks()

    assert str(panel.save_button["state"]) == "disabled"
    assert panel.message_for("filter.radius_km") != ""
    root.destroy()


# --- T-141 · The networks as a reorderable list (REQ-GUI-008, CA-110.8) ----------


def test_the_list_holds_the_four_networks_in_declared_order(panel: PanelModel) -> None:
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)

    assert [n.label for n in networks.entries] == ["EMSC", "USGS", "FUNVISIS", "GEOFON"]
    assert all(n.enabled for n in networks.entries)


def test_the_list_opens_on_the_order_the_file_declares(config_file: Path) -> None:
    from vigia_eew.notify.config_panel import NetworkList

    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace(
            "# priority = 1   # see [sources.emsc] above", "priority = 1"
        ),
        encoding="utf-8",
    )
    networks = NetworkList(PanelModel(ConfigWriter(config_file)))

    assert [n.label for n in networks.entries][0] == "FUNVISIS"


def test_moving_a_network_up_changes_the_order(panel: PanelModel) -> None:
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)
    networks.move_up("sources_geofon")

    assert [n.label for n in networks.entries] == ["EMSC", "USGS", "GEOFON", "FUNVISIS"]


def test_the_first_network_cannot_move_up(panel: PanelModel) -> None:
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)
    networks.move_up("sources_emsc")

    assert [n.label for n in networks.entries][0] == "EMSC"


def test_the_last_network_cannot_move_down(panel: PanelModel) -> None:
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)
    networks.move_down("sources_geofon")

    assert [n.label for n in networks.entries][-1] == "GEOFON"


def test_reordering_and_saving_produces_a_file_in_the_same_order(
    panel: PanelModel, config_file: Path
) -> None:
    """CA-110.8: what the user sees and what the file says are the same list."""
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)
    networks.move_up("sources_funvisis")
    networks.move_up("sources_funvisis")
    shown = [n.label for n in networks.entries]

    panel.save()

    reloaded = load_config(config_file)
    by_priority = sorted(
        ("EMSC", "USGS", "FUNVISIS", "GEOFON"),
        key=lambda name: getattr(reloaded, f"sources_{name.lower()}").priority,
    )
    assert by_priority == shown == ["FUNVISIS", "EMSC", "USGS", "GEOFON"]


def test_reordering_declares_a_priority_for_every_network(panel: PanelModel) -> None:
    """Once an order is expressed in the interface, all four carry a number.

    Leaving some unranked would mean the list shown and the list stored could
    drift apart the moment a later version changed the declaration order.
    """
    from vigia_eew.notify.config_panel import NetworkList

    NetworkList(panel).move_up("sources_geofon")

    assert sorted(panel.changes()) == [
        "sources.emsc.priority",
        "sources.funvisis.priority",
        "sources.geofon.priority",
        "sources.usgs.priority",
    ]


def test_disabling_a_network_is_one_change_and_keeps_the_others(
    panel: PanelModel, config_file: Path
) -> None:
    """CA-110.5 from the interface: the flag decides existence, nothing else."""
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)
    networks.set_enabled("sources_funvisis", False)

    assert panel.changes() == {"sources.funvisis.enabled": False}
    panel.save()
    reloaded = load_config(config_file)
    assert reloaded.sources_funvisis.enabled is False
    assert reloaded.sources_emsc.enabled is True


def test_a_disabled_network_stays_in_the_list(panel: PanelModel) -> None:
    """It has to be visible to be re-enabled; disabled is not deleted."""
    from vigia_eew.notify.config_panel import NetworkList

    networks = NetworkList(panel)
    networks.set_enabled("sources_geofon", False)

    entry = next(n for n in networks.entries if n.key == "sources_geofon")
    assert entry.enabled is False
    assert len(networks.entries) == 4


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_reordering_in_the_real_panel_reaches_the_file(tmp_path: Path) -> None:
    """CA-110.8 through the widgets: the list, the model and the file agree."""
    import tkinter as tk

    from vigia_eew.notify.config_panel import ConfigPanel

    path = tmp_path / "config.toml"
    path.write_text(bundled_example(), encoding="utf-8")
    root = tk.Tk()
    panel = ConfigPanel(root, PanelModel(ConfigWriter(path)))
    root.update_idletasks()

    panel.networks.move_up("sources_geofon")
    panel._order_network_rows()
    panel._show_values()
    root.update_idletasks()
    shown = [n.label for n in panel.networks.entries]
    panel.model.save()

    reloaded = load_config(path)
    stored = sorted(
        ("EMSC", "USGS", "FUNVISIS", "GEOFON"),
        key=lambda name: getattr(reloaded, f"sources_{name.lower()}").priority,
    )
    assert stored == shown
    assert panel.controls["sources.geofon.priority"].get() == "3"
    root.destroy()
