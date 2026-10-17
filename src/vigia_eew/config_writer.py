"""Writing `config.toml` without destroying it (REQ-CFG-009..012, ADR-019).

The agent has only ever *read* its configuration. ADR-007 chose `tomllib` --
the standard library's reader, which has no writer -- and wrote down the
consequence: "writing config isn't needed in v1". The configuration panel
contradicts that, so amendment [E-02] and ADR-019 come first; this module is
what they permit.

Four properties, and none of them is an implementation detail:

  - **The comments survive.** The shipped file carries 46 lines of them, and
    they are the only in-line help the user has. `tomlkit` edits the parsed
    document in place instead of re-serialising a model, so a save changes
    the line it was asked to change and nothing else (REQ-CFG-009).
  - **The write is atomic, with the previous version recoverable.** Temp file
    plus `os.replace`, the same rule that already governs `state.json`, plus a `.bak` copy
    written before the replace -- the order matters, and why is in
    [[lat.md/configuration#The backup is written before the rename, not after]]
    (REQ-CFG-010).
  - **An external edit is a conflict, not a race.** This is the first
    component that writes a file the user also edits by hand. The fingerprint
    taken at load is compared before writing; a mismatch refuses the save and
    names the file (REQ-CFG-011).
  - **Validation happens before the disk is touched.** Everything is applied
    to an in-memory copy of the document and validated against the same
    `Settings` schema the agent starts with. An invalid configuration on disk
    leaves the agent unable to start, so it never gets there (REQ-CFG-012,
    Art. 3).

`tomllib` remains the reader. This module is imported only on the write path,
so the agent's startup is untouched.

[E-02]: docs/v1/00-ENMIENDAS-CONSTITUCION.md
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomlkit
from pydantic import BaseModel, ValidationError
from tomlkit import TOMLDocument
from tomlkit.items import Table

from vigia_eew.config import SECTION_PATHS, Settings, bundled_example, map_toml_keys

#: Suffix of the recoverable copy of the previous version (DATA-MODEL §3).
BACKUP_SUFFIX = ".bak"

#: How the file's identity is captured at load time: modification time and
#: size. Not a hash -- the point is to notice somebody else's write, not to
#: re-read the whole file on every save.
Fingerprint = tuple[int, int]


class ExternalEdit(RuntimeError):
    """The file changed on disk after it was loaded (REQ-CFG-011).

    Raised instead of writing. The caller's way out is to load again, which
    is what makes this a conflict the user resolves rather than a dead end.
    """


class InvalidConfig(ValueError):
    """The requested values do not validate, so nothing was written (REQ-CFG-012)."""


def fingerprint_of(path: Path) -> Fingerprint | None:
    """The file's modification time and size, or None when it does not exist."""
    try:
        info = path.stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def _model_for(section: tuple[str, ...]) -> type[BaseModel] | None:
    """The configuration model a TOML section path belongs to, if any."""
    for field, toml_path in SECTION_PATHS.items():
        if toml_path == section:
            annotation = Settings.model_fields[field].annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                return annotation
    return None


def _check_known(dotted: str) -> tuple[tuple[str, ...], str]:
    """Splits `"filter.radius_km"` into its section path and leaf, or rejects it.

    A key the schema does not know would be written to the file and then
    dropped by the loader, which reads as a setting that simply has no
    effect -- the user's line sits there looking applied.
    """
    parts = dotted.split(".")
    if len(parts) < 2:
        raise InvalidConfig(f"{dotted!r} is not a section.field path")
    section, leaf = tuple(parts[:-1]), parts[-1]
    model = _model_for(section)
    if model is None:
        raise InvalidConfig(f"unknown configuration section: {'.'.join(section)!r}")
    if leaf not in model.model_fields:
        raise InvalidConfig(f"unknown configuration field: {dotted!r}")
    return section, leaf


def _table_at(document: TOMLDocument, section: tuple[str, ...]) -> Any:
    """The table for `section`, creating the tables that do not exist yet.

    `[reference]` ships commented out, so setting a reference point for the
    first time genuinely has to create the table rather than edit one.
    """
    node: Any = document
    for name in section:
        existing = node.get(name)
        if existing is None:
            created: Table = tomlkit.table()
            node[name] = created
            node = created
        else:
            node = existing
    return node


class ConfigWriter:
    """Loads `config.toml`, applies changes, and writes it back intact."""

    def __init__(self, path: Path | str, *, logger: logging.Logger | None = None) -> None:
        self.path = Path(path)
        self._log = logger or logging.getLogger("vigia_eew.config_writer")
        self._document: TOMLDocument = tomlkit.document()
        self._fingerprint: Fingerprint | None = None
        self._loaded = False

    @property
    def fingerprint(self) -> Fingerprint | None:
        """The file's fingerprint as of the last `load()`; None if there was no file."""
        return self._fingerprint

    def load(self) -> dict[str, Any]:
        """Reads the file (or the shipped template) and returns what it declares.

        The mapping is what the file *says*, not the effective configuration:
        a section the file omits is absent here. That distinction is what lets
        the panel leave `[reference]` alone when the user never touched it,
        which is what keeps the IP auto-detection working (RF-33).

        Deliberately does not validate. A file that is already invalid still
        has to be openable -- otherwise the one tool that could fix it is the
        one thing the user cannot start.
        """
        text = self.path.read_text(encoding="utf-8") if self.path.exists() else bundled_example()
        self._document = tomlkit.parse(text)
        self._fingerprint = fingerprint_of(self.path)
        self._loaded = True
        return dict(self._document.unwrap())

    def save(self, changes: Mapping[str, Any]) -> Settings:
        """Applies `changes` and writes the file atomically; returns what it now holds.

        Args:
            changes: values keyed by their dotted path **in the file**
                (`"filter.radius_km"`, `"sources.emsc.priority"`). Only the
                keys given are touched; everything else keeps the bytes it had.

        Raises:
            ExternalEdit: the file changed on disk since `load()`.
            InvalidConfig: a key is unknown, or the result fails validation.
                Nothing is written.
            OSError: the write itself failed. The original is left intact.
        """
        if not self._loaded:
            self.load()
        self._refuse_if_edited_elsewhere()

        document = tomlkit.parse(tomlkit.dumps(self._document))
        for dotted, value in changes.items():
            section, leaf = _check_known(dotted)
            _table_at(document, section)[leaf] = value

        settings = _validated(document)
        self._write(tomlkit.dumps(document))
        self._document = document
        self._fingerprint = fingerprint_of(self.path)
        self._log.info("config_saved path=%s fields=%d", self.path, len(changes))
        return settings

    def _refuse_if_edited_elsewhere(self) -> None:
        if fingerprint_of(self.path) != self._fingerprint:
            raise ExternalEdit(
                f"{self.path} changed on disk after it was loaded; "
                "reload it before saving so the other edit is not lost"
            )

    def _write(self, content: str) -> None:
        """Backup, temp file, atomic rename -- in that order, and for that reason.

        The backup is written first because the window it protects is the one
        between "the original is gone" and "the new file is in place". The
        temp file lives in the destination directory so the rename stays on
        one filesystem, which is what makes it atomic.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            backup = self.path.with_name(self.path.name + BACKUP_SUFFIX)
            backup.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def _validated(document: TOMLDocument) -> Settings:
    """The schema, applied to the document before the disk hears about it."""
    try:
        return Settings(**map_toml_keys(dict(document.unwrap())))
    except ValidationError as exc:
        raise InvalidConfig(str(exc)) from exc
    except ValueError as exc:
        # `Severity.model_post_init` raises plainly, not as a ValidationError:
        # the cross-field rule (CA-108.4) arrives here, not above.
        raise InvalidConfig(f"severity: {exc}") from exc
