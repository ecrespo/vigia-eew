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
  - `ConfigPanel` is the widget tree, and does no deciding at all.
"""

from __future__ import annotations

import types
import zoneinfo
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError

from vigia_eew.config import SECTION_PATHS, SOURCE_SECTIONS, Settings, by_priority
from vigia_eew.config_writer import ConfigWriter, InvalidConfig

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


# --- The widget tree -------------------------------------------------------------


class Control(Protocol):
    """What the panel needs of a control: it shows a value, and it holds one."""

    def set(self, value: Any) -> None: ...

    def get(self) -> Any: ...


class _Control:
    """One Tk control over one field, reporting every edit to the model."""

    def __init__(self, parent: Any, spec: FieldSpec, on_edit: Callable[[str, Any], None]) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.spec = spec
        self._on_edit = on_edit
        self._variable: Any = tk.BooleanVar() if spec.kind == "bool" else tk.StringVar()
        if spec.kind == "bool":
            self.widget: Any = ttk.Checkbutton(parent, variable=self._variable)
        elif spec.kind == "choice":
            values = list(spec.choices)
            self.widget = ttk.Combobox(parent, textvariable=self._variable, values=values, width=28)
        else:
            self.widget = ttk.Entry(parent, textvariable=self._variable, width=30)
        self._variable.trace_add("write", self._changed)

    def set(self, value: Any) -> None:
        self._variable.set(value if self.spec.kind == "bool" else ("" if value is None else value))

    def get(self) -> Any:
        return self._variable.get()

    def _changed(self, *_args: object) -> None:
        self._on_edit(self.spec.path, self._variable.get())


class _PositionControl:
    """A network's priority, shown as its place in the list.

    It is a control in the sense that matters to CA-108.1: the field is
    reachable and changeable from the interface. What changes it is the pair
    of arrows next to it, not typing a number into it.
    """

    def __init__(self, label: Any) -> None:
        self._label = label

    def set(self, value: Any) -> None:
        self._label.configure(text="-" if value is None else str(value))

    def get(self) -> Any:
        return str(self._label["text"])


class ConfigPanel:
    """The panel itself: collapsible sections, live errors, save and restore.

    Holds no rules. Every decision it displays was made by `PanelModel`, which
    is why the rules are testable without a screen and this is not.
    """

    def __init__(
        self,
        master: Any,
        model: PanelModel,
        *,
        on_saved: Callable[[SaveOutcome], None] | None = None,
    ) -> None:
        from tkinter import ttk

        self.model = model
        self._on_saved = on_saved
        self._frame = ttk.Frame(master, padding=8)
        self._frame.pack(fill="both", expand=True)
        self.controls: dict[str, Control] = {}
        self._messages: dict[str, Any] = {}
        self._open: dict[str, bool] = {}
        self._sections_ui: dict[str, tuple[Any, Any]] = {}
        self._loading = False
        self.networks = NetworkList(model)
        # `enabled` and `priority` belong to the list: one setting, one
        # control. A checkbox in the section *and* a row in the list would be
        # two widgets over one field, and the loser is whichever the user
        # touched first.
        self._owned_by_the_list = {
            f"{_toml(key)}.{name}" for key in SOURCE_SECTIONS for name in ("enabled", "priority")
        }
        self._build_networks()
        self._build_sections()
        self._build_footer()
        self._show_values()

    # --- Construction ---

    def _build_sections(self) -> None:
        from tkinter import ttk

        for section in self.model.sections:
            header = ttk.Button(
                self._frame,
                text=f"▸ {section.title}",
                command=lambda key=section.key: self._toggle(key),  # type: ignore[misc]
            )
            header.pack(fill="x", pady=(6, 0))
            body = ttk.Frame(self._frame, padding=(16, 4))
            self._open[section.key] = False
            self._sections_ui[section.key] = (header, body)
            for row, field in enumerate(section.fields):
                if field.path in self._owned_by_the_list:
                    continue
                ttk.Label(body, text=field.label).grid(row=row, column=0, sticky="w")
                control = _Control(body, field, self._edited)
                control.widget.grid(row=row, column=1, sticky="w", padx=6)
                self.controls[field.path] = control
                message = ttk.Label(body, text="", foreground="#B00020")
                message.grid(row=row, column=2, sticky="w")
                self._messages[field.path] = message
            section_message = ttk.Label(body, text="", foreground="#B00020")
            section_message.grid(row=len(section.fields), column=0, columnspan=3, sticky="w")
            self._messages[section.key] = section_message

    def _build_networks(self) -> None:
        """The four networks as a list: enable each, and order them (REQ-GUI-008)."""
        from tkinter import ttk

        ttk.Label(self._frame, text="Networks, in order of preference").pack(anchor="w")
        self._network_frame = ttk.Frame(self._frame, padding=(16, 4))
        self._network_frame.pack(fill="x")
        specs = {field.path: field for section in self.model.sections for field in section.fields}
        self._network_rows = {}
        for entry in self.networks.entries:
            row = ttk.Frame(self._network_frame)
            enabled_path = f"{_toml(entry.key)}.enabled"
            control = _Control(row, specs[enabled_path], self._edited)
            control.widget.pack(side="left")
            self.controls[enabled_path] = control
            ttk.Label(row, text=entry.label, width=12).pack(side="left")
            position = ttk.Label(row, text="", width=3)
            position.pack(side="left")
            self.controls[f"{_toml(entry.key)}.priority"] = _PositionControl(position)
            ttk.Button(row, text="▲", width=3, command=self._mover(entry.key, up=True)).pack(
                side="left"
            )
            ttk.Button(row, text="▼", width=3, command=self._mover(entry.key, up=False)).pack(
                side="left"
            )
            self._network_rows[entry.key] = row
        self._order_network_rows()

    def _mover(self, key: str, *, up: bool) -> Callable[[], None]:
        def move() -> None:
            if up:
                self.networks.move_up(key)
            else:
                self.networks.move_down(key)
            self._order_network_rows()
            self._show_values()

        return move

    def _order_network_rows(self) -> None:
        for entry in self.networks.entries:
            self._network_rows[entry.key].pack_forget()
        for entry in self.networks.entries:
            self._network_rows[entry.key].pack(fill="x")

    def _build_footer(self) -> None:
        from tkinter import ttk

        footer = ttk.Frame(self._frame, padding=(0, 10))
        footer.pack(fill="x")
        self.save_button = ttk.Button(footer, text="Save", command=self._save)
        self.save_button.pack(side="right")
        restore = ttk.Button(footer, text="Restore defaults", command=self._restore)
        restore.pack(side="right", padx=6)
        self.status = ttk.Label(footer, text="")
        self.status.pack(side="left")

    # --- Behaviour ---

    def _toggle(self, key: str) -> None:
        header, body = self._sections_ui[key]
        self._open[key] = not self._open[key]
        title = next(s.title for s in self.model.sections if s.key == key)
        header.configure(text=f"{'▾' if self._open[key] else '▸'} {title}")
        if self._open[key]:
            body.pack(fill="x", after=header)
        else:
            body.pack_forget()

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
            label.configure(text=errors.get(where, ""))
        self.save_button.configure(state="normal" if self.model.can_save else "disabled")

    def message_for(self, where: str) -> str:
        """The message currently shown next to a field, or its section."""
        return str(self._messages[where]["text"])

    def _restore(self) -> None:
        self.model.restore_defaults()
        self._show_values()

    def _save(self) -> None:
        try:
            outcome = self.model.save()
        except Exception as exc:  # noqa: BLE001 - every failure belongs on screen
            self.status.configure(text=str(exc))
            return
        self.status.configure(text="Saved. The changes apply when the agent restarts.")
        if self._on_saved is not None:
            self._on_saved(outcome)
