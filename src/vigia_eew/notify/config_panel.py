"""The configuration panel, generated from the schema (REQ-GUI-001..004, ADR-020).

The user this product is written for should not have to open a text file and
learn its syntax to find out whether an earthquake affects them. The panel is
the other way in; the file stays exactly what it was
([[lat.md/configuration#The file is still the source of truth, and the panel is another way in]]).

**The controls are derived from the configuration models, not written one by
one.** Forty-odd fields transcribed by hand is forty-odd chances for a field
added to the model never to reach the interface, and nobody finds out until a
user cannot find the option. Here the type of the field chooses the control and
its constraints do the validating, so a field added to `config.py` appears here
by itself -- and one whose shape the generator does not understand stops the
panel by name rather than disappearing from it (CA-108.2).

ADR-020's honest cost is `CHOICES`: a few fields have a closed domain the
schema does not express -- language, log level, timezone -- and they carry a
control declared by hand. The coverage test accepts those because they are
declared, not because they are forgotten.

The module is in two halves, and the seam is the point:

  - `describe` and `PanelModel` are pure. Which controls exist, what a value
    means, whether it validates, and what is ultimately written are decided
    without a display and tested without one.
  - `ConfigPanel` is the widget tree -- Flet controls laid out responsively
    (ADR-030) -- and does no deciding at all.
"""

from __future__ import annotations

import types
import zoneinfo
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, Union, get_args, get_origin

import flet as ft
from pydantic import BaseModel, ValidationError

from vigia_eew.config import SECTION_PATHS, SOURCE_SECTIONS, Settings, by_priority
from vigia_eew.config_writer import ConfigWriter, InvalidConfig
from vigia_eew.notify import ui_scale

FieldKind = Literal["bool", "int", "float", "str", "choice"]

#: Log levels the logging configuration accepts (`logging_conf.py`).
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: Languages the product ships (RF-35), plus OS detection.
_LANGUAGES = ("auto", "en", "es")


def _timezones() -> tuple[str, ...]:
    """The IANA zones this interpreter can resolve, sorted.

    Falls back to the product's own default rather than an empty list: a
    machine whose tzdata cannot be enumerated still has to be configurable,
    and the field is validated when the agent starts either way.
    """
    try:
        available = sorted(zoneinfo.available_timezones())
    except Exception:  # noqa: BLE001 - a missing tz database must not break the panel
        available = []
    return tuple(available) or ("UTC", "America/Caracas")


#: Fields whose domain is closed but not expressed in the schema -- the
#: declared exception of ADR-020. A list, not free text, because typing
#: "Amercia/Caracas" produces a configuration that starts and silently shows
#: the wrong local time.
CHOICES: dict[str, tuple[str, ...]] = {
    "notification.language": _LANGUAGES,
    "notification.timezone": _timezones(),
    "logging.level": _LOG_LEVELS,
}

#: Sections in the order the panel shows them, with the title each one carries.
SECTION_TITLES: dict[str, str] = {
    "reference": "Reference point",
    "filter": "Filter",
    "sources_emsc": "Source · EMSC",
    "sources_usgs": "Source · USGS",
    "sources_funvisis": "Source · FUNVISIS",
    "sources_geofon": "Source · GEOFON",
    "dedup": "Deduplication",
    "severity": "Severity",
    "notification": "Notification",
    "logging": "Logging",
    "history": "History",
}


class UnsupportedField(TypeError):
    """A configuration field the generator cannot render (CA-108.2).

    Raised rather than skipped. A field quietly missing from the panel is the
    exact failure the generation exists to prevent, and it would look like a
    panel that simply does not offer the option.
    """


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One control, derived from one field of the configuration schema."""

    path: str
    section: str
    name: str
    kind: FieldKind
    default: Any
    optional: bool = False
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    exclusive_minimum: float | None = None
    maximum: float | None = None

    @property
    def label(self) -> str:
        """The field's name as a person reads it."""
        return self.name.replace("_", " ").replace(" s", " (s)").capitalize()


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """One collapsible group of controls -- one table of the file."""

    key: str
    toml_path: tuple[str, ...]
    title: str
    model: type[BaseModel]
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True, slots=True)
class SaveOutcome:
    """What a successful save produced, and what the user still has to do."""

    settings: Settings
    #: Always true today. The configuration is read once, at startup: the
    #: filter, the normalizer and the four ingestors receive theirs when they
    #: are built. Saying otherwise would be a lie until REQ-GUI-007 exists
    #: (CA-108.9).
    restart_required: bool = True


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """`int | None` -> `(int, True)`; anything else unchanged."""
    if get_origin(annotation) in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def _kind_of(annotation: Any, path: str) -> FieldKind:
    """Which control renders this field, or `UnsupportedField` naming it."""
    if path in CHOICES:
        return "choice"
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is str:
        return "str"
    raise UnsupportedField(
        f"{path}: no control for {annotation!r}. Declare one rather than "
        "leaving the field out of the panel."
    )


def _bounds(metadata: list[Any]) -> tuple[float | None, float | None, float | None]:
    """The `ge`/`gt`/`le` the schema already declares, so nobody restates them."""
    minimum = exclusive = maximum = None
    for item in metadata:
        minimum = getattr(item, "ge", None) if minimum is None else minimum
        exclusive = getattr(item, "gt", None) if exclusive is None else exclusive
        maximum = getattr(item, "le", None) if maximum is None else maximum
    return minimum, exclusive, maximum


def describe(
    settings_type: type[BaseModel] = Settings,
    section_paths: Mapping[str, tuple[str, ...]] = SECTION_PATHS,
) -> tuple[SectionSpec, ...]:
    """Walks the configuration schema and returns the panel it implies."""
    sections: list[SectionSpec] = []
    for key, toml_path in section_paths.items():
        model = settings_type.model_fields[key].annotation
        if not (isinstance(model, type) and issubclass(model, BaseModel)):  # pragma: no cover
            raise UnsupportedField(f"{key}: a configuration section must be a model")
        fields = []
        for name, info in model.model_fields.items():
            path = ".".join((*toml_path, name))
            annotation, optional = _unwrap_optional(info.annotation)
            minimum, exclusive, maximum = _bounds(list(info.metadata))
            fields.append(
                FieldSpec(
                    path=path,
                    section=key,
                    name=name,
                    kind=_kind_of(annotation, path),
                    default=_default_of(model, name),
                    optional=optional,
                    choices=CHOICES.get(path, ()),
                    minimum=minimum,
                    exclusive_minimum=exclusive,
                    maximum=maximum,
                )
            )
        sections.append(
            SectionSpec(
                key=key,
                toml_path=tuple(toml_path),
                title=SECTION_TITLES.get(key, key),
                model=model,
                fields=tuple(fields),
            )
        )
    return tuple(sections)


def _default_of(model: type[BaseModel], name: str) -> Any:
    """The field's default as the model itself produces it."""
    info = model.model_fields[name]
    if info.default_factory is not None:  # pragma: no cover - no section nests another
        return info.default_factory()  # type: ignore[call-arg]
    return info.default


class PanelModel:
    """What the panel shows, what it validates, and what it will write.

    Holds no widgets on purpose: every decision here is testable without a
    display, which is what makes the rules the panel enforces checkable at all.
    """

    def __init__(self, writer: ConfigWriter, *, sections: tuple[SectionSpec, ...] | None = None):
        self._writer = writer
        self._sections = sections if sections is not None else describe()
        self._specs = {field.path: field for section in self._sections for field in section.fields}
        self._values: dict[str, Any] = {}
        self._baseline: dict[str, Any] = {}
        self._declared: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self.reload()

    # --- Reading ---

    @property
    def sections(self) -> tuple[SectionSpec, ...]:
        return self._sections

    @property
    def errors(self) -> dict[str, str]:
        """Messages by field path, plus by section key for rules between fields."""
        return dict(self._errors)

    @property
    def can_save(self) -> bool:
        """CA-108.3: nothing is written while anything on screen is wrong."""
        return not self._errors

    def value(self, path: str) -> Any:
        return self._values[path]

    def declared(self, path: str) -> bool:
        """Whether the **file** sets this field, as opposed to the panel defaulting it.

        The distinction is what keeps `[reference]` commented out when nobody
        touched it, and its absence is what enables the IP detection (RF-33).
        """
        return path in self._declared

    def reload(self) -> None:
        """Reads the file again -- the way out of a conflict (CA-108.7)."""
        self._declared = _flatten(self._writer.load(), self._sections)
        self._values = {
            path: self._declared.get(path, spec.default) for path, spec in self._specs.items()
        }
        self._baseline = dict(self._values)
        self._errors = {}

    # --- Editing ---

    def edit(self, path: str, raw: Any) -> None:
        """Takes what the control holds, and validates it immediately (REQ-GUI-002)."""
        spec = self._specs[path]
        try:
            self._values[path] = _coerce(raw, spec)
        except ValueError as exc:
            self._values[path] = raw
            self._errors[path] = str(exc)
            return
        self._errors.pop(path, None)
        self._revalidate(spec.section)

    def restore_defaults(self, section: str | None = None) -> None:
        """Proposes the schema's defaults; nothing is written until a save (REQ-GUI-003)."""
        for path, spec in self._specs.items():
            if section is None or spec.section == section:
                self._values[path] = spec.default
                self._errors.pop(path, None)
        for spec_section in {s.key for s in self._sections} if section is None else {section}:
            self._revalidate(spec_section)

    def changes(self) -> dict[str, Any]:
        """Only what the user actually changed, keyed for the writer.

        A panel that wrote every field it displayed would fill in sections the
        file deliberately leaves out, and `[reference]` is the one that matters.
        """
        return {
            path: value for path, value in self._values.items() if value != self._baseline[path]
        }

    # --- Saving ---

    def save(self) -> SaveOutcome:
        """Writes the changes and reports that the agent has to be restarted.

        Raises:
            InvalidConfig: something on screen does not validate, so nothing
                was written. The writer validates again before the disk is
                touched -- two barriers, on purpose (ADR-019).
            ExternalEdit: the file changed since it was loaded.
        """
        if self._errors:
            raise InvalidConfig("; ".join(f"{where}: {why}" for where, why in self._errors.items()))
        settings = self._writer.save(self.changes())
        self._declared = _flatten(self._writer.load(), self._sections)
        self._baseline = dict(self._values)
        return SaveOutcome(settings=settings)

    # --- Validation ---

    def _revalidate(self, section_key: str) -> None:
        """Runs the section's own model over what the panel holds.

        The same schema the agent validates with at startup, so there is one
        place where the rule lives. A failure that names a field lands on that
        field; one that does not -- the severity thresholds are the case -- is
        a rule between fields and belongs to the section (CA-108.4).
        """
        section = next(s for s in self._sections if s.key == section_key)
        self._errors.pop(section_key, None)
        values = {
            field.name: self._values[field.path]
            for field in section.fields
            if field.path not in self._errors
        }
        try:
            section.model(**values)
        except ValidationError as exc:
            self._record(section, exc)
        except ValueError as exc:
            # `model_post_init` raises plainly: a rule between two fields,
            # where neither one is wrong on its own.
            self._errors[section_key] = str(exc)

    def _record(self, section: SectionSpec, failure: ValidationError) -> None:
        for error in failure.errors():
            name = str(error["loc"][0]) if error["loc"] else ""
            path = ".".join((*section.toml_path, name))
            if path in self._specs:
                self._errors[path] = error["msg"]
            else:  # pragma: no cover - pydantic always names the field it rejected
                self._errors[section.key] = error["msg"]


@dataclass(frozen=True, slots=True)
class NetworkEntry:
    """One seismic network as the list shows it."""

    key: str
    label: str
    enabled: bool


class NetworkList:
    """The four networks as an orderable list (REQ-GUI-008, CA-110.8).

    A list rather than four numeric fields because the user is expressing an
    *order*, and typing four numbers that have to stay distinct is a way of
    asking them to do the interface's job.

    Changes go straight into `PanelModel`, so the list saves, validates and
    reverts through exactly the same path as every other control -- and
    reordering it is not applied until the same Save.
    """

    def __init__(self, model: PanelModel) -> None:
        self._model = model
        self._order = list(by_priority([(key, self._priority(key)) for key in SOURCE_SECTIONS]))

    @property
    def entries(self) -> tuple[NetworkEntry, ...]:
        return tuple(
            NetworkEntry(key=key, label=_network_label(key), enabled=bool(self._enabled(key)))
            for key in self._order
        )

    def move_up(self, key: str) -> None:
        self._move(key, -1)

    def move_down(self, key: str) -> None:
        self._move(key, 1)

    def set_enabled(self, key: str, enabled: bool) -> None:
        """Turning a network off leaves it in the list; disabled is not deleted."""
        self._model.edit(f"{_toml(key)}.enabled", enabled)

    def _move(self, key: str, step: int) -> None:
        position = self._order.index(key)
        target = position + step
        if not 0 <= target < len(self._order):
            return
        self._order[position], self._order[target] = self._order[target], self._order[position]
        self._apply()

    def _apply(self) -> None:
        """Writes the shown order back as consecutive priorities.

        All four, not only the ones that moved: once an order has been
        expressed in the interface, leaving some unranked would let the list
        shown and the list stored drift apart the moment a later version
        changed the declaration order.
        """
        for position, key in enumerate(self._order, start=1):
            self._model.edit(f"{_toml(key)}.priority", position)

    def _priority(self, key: str) -> int | None:
        value = self._model.value(f"{_toml(key)}.priority")
        return value if isinstance(value, int) else None

    def _enabled(self, key: str) -> Any:
        return self._model.value(f"{_toml(key)}.enabled")


def _toml(section_key: str) -> str:
    """`"sources_emsc"` -> `"sources.emsc"`, the path the file uses."""
    return ".".join(SECTION_PATHS[section_key])


def _network_label(section_key: str) -> str:
    return section_key.removeprefix("sources_").upper()


def _table_for(declared: Mapping[str, Any], toml_path: tuple[str, ...]) -> Mapping[str, Any]:
    """The file's table at `toml_path`, or an empty one when the file omits it."""
    table: Any = declared
    for part in toml_path:
        table = table.get(part) if isinstance(table, Mapping) else None
    return table if isinstance(table, Mapping) else {}


def _flatten(declared: Mapping[str, Any], sections: tuple[SectionSpec, ...]) -> dict[str, Any]:
    """The file's nested tables as dotted paths, keeping only what it declares."""
    flat: dict[str, Any] = {}
    for section in sections:
        table = _table_for(declared, section.toml_path)
        for field in section.fields:
            if field.name in table:
                flat[field.path] = table[field.name]
    return flat


def _coerce(raw: Any, spec: FieldSpec) -> Any:
    """Turns what a control holds into what the schema expects."""
    if spec.kind == "bool":
        return bool(raw)
    text = str(raw).strip()
    if text == "":
        if spec.optional:
            return None
        raise ValueError("this field cannot be empty")
    if spec.kind in ("int", "float"):
        try:
            return int(text) if spec.kind == "int" else float(text)
        except ValueError:
            raise ValueError(f"must be a number ({spec.kind})") from None
    return text


# --- The controls ----------------------------------------------------------------


class Control(Protocol):
    """What the panel needs of a control: it shows a value, and it holds one."""

    def set(self, value: Any) -> None: ...

    def get(self) -> Any: ...


def _bounds_hint(spec: FieldSpec) -> str | None:
    """The range the schema enforces, phrased as a hint under the field."""
    parts = []
    if spec.minimum is not None:
        parts.append(f"≥ {spec.minimum:g}")
    if spec.exclusive_minimum is not None:
        parts.append(f"> {spec.exclusive_minimum:g}")
    if spec.maximum is not None:
        parts.append(f"≤ {spec.maximum:g}")
    hint = ", ".join(parts)
    if spec.optional:
        hint = f"{hint} (optional)" if hint else "optional"
    return hint or None


class _Control:
    """One Flet control over one field, reporting every edit to the model.

    The type of the field chooses the control: a switch for a flag, a menu
    for a closed domain (filterable -- the timezone list has ~600 entries),
    a text field for everything else, with a numeric keyboard for numbers.
    """

    def __init__(self, spec: FieldSpec, on_edit: Callable[[str, Any], None]) -> None:
        self.spec = spec
        self._on_edit = on_edit
        if spec.kind == "bool":
            self.widget: Any = ft.Switch(label=spec.label, on_change=self._changed)
        elif spec.kind == "choice":
            self.widget = ft.Dropdown(
                label=spec.label,
                options=[ft.DropdownOption(key=choice, text=choice) for choice in spec.choices],
                enable_filter=len(spec.choices) > 12,
                editable=len(spec.choices) > 12,
                menu_height=360,
                expand=True,
                on_select=self._changed,
            )
        else:
            numeric = spec.kind in ("int", "float")
            self.widget = ft.TextField(
                label=spec.label,
                helper=_bounds_hint(spec),
                keyboard_type=ft.KeyboardType.NUMBER if numeric else ft.KeyboardType.TEXT,
                dense=True,
                on_change=self._changed,
            )

    def set(self, value: Any) -> None:
        if self.spec.kind == "bool":
            self.widget.value = bool(value)
        else:
            self.widget.value = "" if value is None else str(value)

    def get(self) -> Any:
        return self.widget.value

    def _changed(self, _event: Any = None) -> None:
        self._on_edit(self.spec.path, self.widget.value)


class _PositionControl:
    """A network's priority, shown as its place in the list.

    It is a control in the sense that matters to CA-108.1: the field is
    reachable and changeable from the interface. What changes it is the pair
    of arrows next to it, not typing a number into it.
    """

    def __init__(self) -> None:
        self.widget = ft.Text("-", weight=ft.FontWeight.BOLD, width=24)

    def set(self, value: Any) -> None:
        self.widget.value = "-" if value is None else str(value)

    def get(self) -> Any:
        return str(self.widget.value)


# --- The panel ---------------------------------------------------------------------


class ConfigPanel:
    """The panel itself: collapsible sections, live errors, save and restore.

    Holds no rules. Every decision it displays was made by `PanelModel`, which
    is why the rules are testable without a screen.

    **Responsive** (ADR-030): the fields of a section sit in a `ResponsiveRow`,
    so they take one column on a narrow window, two from the `md` breakpoint
    and three from `xl` (`ui_scale.FIELD_COLUMNS`). The body scrolls under a
    footer that does not -- the Save button is the one control whose absence
    makes the panel useless rather than awkward (T-151).

    `view` is the root control; the caller puts it on a page. Building it
    needs no page, which is what lets the tests drive the real controls.
    """

    def __init__(
        self,
        model: PanelModel,
        *,
        on_saved: Callable[[SaveOutcome], None] | None = None,
        on_about: Callable[[], None] | None = None,
        about_label: str = "About…",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.model = model
        self._on_saved = on_saved
        self._on_about = on_about
        self._about_label = about_label
        self._on_close = on_close
        self.controls: dict[str, Control] = {}
        self._messages: dict[str, Any] = {}
        self._sections_ui: dict[str, Any] = {}
        self._loading = False
        self.networks = NetworkList(model)
        # `enabled` and `priority` belong to the list: one setting, one
        # control. A checkbox in the section *and* a row in the list would be
        # two widgets over one field, and the loser is whichever the user
        # touched first.
        self._owned_by_the_list = {
            f"{_toml(key)}.{name}" for key in SOURCE_SECTIONS for name in ("enabled", "priority")
        }
        body = ft.ListView(
            expand=True,
            spacing=12,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            controls=[self._build_networks(), *self._build_sections()],
        )
        self.view = ft.SafeArea(
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[self._build_header(), body, ft.Divider(height=1), self._build_footer()],
            ),
        )
        self._show_values()

    # --- Construction ---

    def _build_header(self) -> Any:
        actions: list[Any] = []
        on_about, on_close = self._on_about, self._on_close
        if on_about is not None:
            # The tray menu is not reachable on every desktop (REQ-GUI-009); the
            # panel is, so what the product is and under what terms is reachable
            # from here too.
            actions.append(
                ft.TextButton(
                    content=ft.Text(self._about_label),
                    icon=ft.Icons.INFO_OUTLINE,
                    on_click=lambda _e: on_about(),
                )
            )
        if on_close is not None:
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    tooltip="Close",
                    on_click=lambda _e: on_close(),
                )
            )
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.PRIMARY),
                    ft.Text(
                        "Vigía-eew · Settings",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        expand=True,
                    ),
                    *actions,
                ],
            ),
        )

    def _build_sections(self) -> list[Any]:
        cards = []
        for section in self.model.sections:
            cells: list[Any] = []
            for field in section.fields:
                if field.path in self._owned_by_the_list:
                    continue
                control = _Control(field, self._edited)
                self.controls[field.path] = control
                message = ft.Text("", color=ft.Colors.ERROR, size=12)
                self._messages[field.path] = message
                cells.append(
                    ft.Column(
                        col=ui_scale.FIELD_COLUMNS,
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[control.widget, message],
                    )
                )
            section_message = ft.Text("", color=ft.Colors.ERROR)
            self._messages[section.key] = section_message
            tile = ft.ExpansionTile(
                title=ft.Text(section.title, weight=ft.FontWeight.W_600),
                expanded=False,
                maintain_state=True,
                controls_padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                controls=[
                    ft.ResponsiveRow(controls=cells, spacing=16, run_spacing=8),
                    section_message,
                ],
            )
            self._sections_ui[section.key] = tile
            cards.append(ft.Card(content=tile))
        return cards

    def _build_networks(self) -> Any:
        """The four networks as a list: enable each, and order them (REQ-GUI-008)."""
        specs = {field.path: field for section in self.model.sections for field in section.fields}
        self._network_rows: dict[str, Any] = {}
        for entry in self.networks.entries:
            enabled_path = f"{_toml(entry.key)}.enabled"
            control = _Control(specs[enabled_path], self._edited)
            control.widget.label = None
            self.controls[enabled_path] = control
            position = _PositionControl()
            self.controls[f"{_toml(entry.key)}.priority"] = position
            self._network_rows[entry.key] = ft.Row(
                controls=[
                    position.widget,
                    control.widget,
                    ft.Text(entry.label, weight=ft.FontWeight.W_600, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.ARROW_UPWARD,
                        tooltip="Move up",
                        on_click=self._mover(entry.key, up=True),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ARROW_DOWNWARD,
                        tooltip="Move down",
                        on_click=self._mover(entry.key, up=False),
                    ),
                ],
            )
        self._network_list = ft.Column(spacing=0)
        self._order_network_rows()
        return ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Networks, in order of preference",
                            weight=ft.FontWeight.W_600,
                        ),
                        self._network_list,
                    ]
                ),
            )
        )

    def _mover(self, key: str, *, up: bool) -> Callable[[Any], None]:
        def move(_event: Any = None) -> None:
            if up:
                self.networks.move_up(key)
            else:
                self.networks.move_down(key)
            self._order_network_rows()
            self._show_values()

        return move

    def _order_network_rows(self) -> None:
        self._network_list.controls = [
            self._network_rows[entry.key] for entry in self.networks.entries
        ]

    def _build_footer(self) -> Any:
        self.save_button = ft.FilledButton(
            content=ft.Text("Save"), icon=ft.Icons.SAVE, on_click=lambda _e: self._save()
        )
        restore = ft.OutlinedButton(
            content=ft.Text("Restore defaults"),
            icon=ft.Icons.RESTORE,
            on_click=lambda _e: self._restore(),
        )
        self.status = ft.Text("", expand=True)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            content=ft.ResponsiveRow(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                run_spacing=8,
                controls=[
                    ft.Container(col={"xs": 12, "md": 6}, content=self.status),
                    ft.Row(
                        col={"xs": 12, "md": 6},
                        alignment=ft.MainAxisAlignment.END,
                        wrap=True,
                        controls=[restore, self.save_button],
                    ),
                ],
            ),
        )

    # --- Behaviour ---

    def toggle(self, key: str) -> None:
        """Opens or closes a section."""
        tile = self._sections_ui[key]
        tile.expanded = not tile.expanded

    def _edited(self, path: str, raw: Any) -> None:
        if self._loading:
            return
        self.model.edit(path, raw)
        self._show_errors()

    def _show_values(self) -> None:
        self._loading = True
        try:
            for path, control in self.controls.items():
                control.set(self.model.value(path))
        finally:
            self._loading = False
        self._show_errors()

    def _show_errors(self) -> None:
        errors = self.model.errors
        for where, label in self._messages.items():
            label.value = errors.get(where, "")
            label.visible = bool(label.value)
        self.save_button.disabled = not self.model.can_save

    def message_for(self, where: str) -> str:
        """The message currently shown next to a field, or its section."""
        return str(self._messages[where].value or "")

    def _restore(self) -> None:
        self.model.restore_defaults()
        self._show_values()

    def _save(self) -> None:
        try:
            outcome = self.model.save()
        except Exception as exc:  # noqa: BLE001 - every failure belongs on screen
            self.status.value = str(exc)
            self.status.color = ft.Colors.ERROR
            return
        self.status.value = "Saved. The changes apply when the agent restarts."
        self.status.color = None
        if self._on_saved is not None:
            self._on_saved(outcome)
