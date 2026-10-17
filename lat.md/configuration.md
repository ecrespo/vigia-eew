# Configuration

`config.toml` is the source of truth, and for six versions it was read-only by decision. ADR-007
chose `tomllib` — the standard library's reader, which has no writer — and recorded the
consequence in one line: *"writing config isn't needed in v1"*.

v1.0 contradicts that, so amendment E-02 and ADR-019 were published **before** any code was
written. [[src/vigia_eew/config_writer.py#ConfigWriter]] is what they permit.

## The file is still the source of truth, and the panel is another way in

The tray keeps its "Edit configuration…" entry alongside the one that opens the panel.

That is not politeness towards old habits: the file is what lets somebody version it with Git, copy
it between machines, and edit it over SSH. Replacing it with a panel would take all three away to
gain nothing.

The reader does not change at all. `tomllib` still parses the file at startup, and
[[src/vigia_eew/config_writer.py#ConfigWriter]] is imported only when something writes — so the
agent's startup path is byte for byte the one that shipped in v0.6.0.

## Why `tomlkit` and not a serialiser

The shipped file carries 46 lines of comments, and they are the only in-line help the user has.
Serialising `Settings` back out would produce a valid file with none of them, and the loss would
be silent and total on the first save.

`tomlkit` parses into a document that remembers its own formatting, so setting one key changes one
line. `tomli-w` was rejected for exactly the property it lacks; a second file merged at read time
was rejected because it creates two sources of truth for the same setting.

## What the writer refuses to do

Three refusals, each protecting something a save could otherwise destroy:

- **It will not write over somebody else's edit.** The panel is the first component that writes a
  file the user also edits by hand. The fingerprint — modification time and size — is taken at
  load and compared before writing; a mismatch raises instead of saving, and the way out is to
  load again. Persisting that fingerprint was rejected: the case it protects lives entirely
  inside one panel session.
- **It will not leave an invalid file on disk.** Everything is applied to an in-memory copy and
  validated against the same `Settings` schema the agent starts with. An invalid `config.toml`
  leaves the agent unable to start, which is Art. 3 territory — so validation happens before the
  disk is touched, not after.
- **It will not write a key the schema does not know.** Pydantic ignores unknown keys, so a typo
  would land in the file, be dropped at load, and sit there looking like a setting that had been
  applied.

## Only what changed is written

The writer takes the fields to change, not a whole configuration.

That is what keeps `[reference]` commented out when the user never touched it — and `[reference]`
being absent is precisely what enables the IP-based location detection (RF-33). A panel that wrote
every field on every save would silently disable that on the first save anybody made.

See [[lat.md/state#Reference point resolution happens once, in the application layer]].

## The backup is written before the rename, not after

Temp file plus `os.replace`, the same rule that governs `state.json`
([[lat.md/state#Persisted state]]), plus a `.bak` copy of the previous version.

The order matters: the window worth protecting is between "the original is gone" and "the new file
is in place", so the copy has to exist before the rename, not after it. One backup and not a
history — the file is meant to be versioned with Git by anyone who cares, and duplicating that
inside the product would add retention management to solve a solved problem.

## The panel is generated, not transcribed

[[src/vigia_eew/notify/config_panel.py#describe]] walks the configuration models and the type of
each field chooses its control; the constraints already on the field do the validating.

Forty-odd controls written by hand is forty-odd chances for a field added to the model never to
reach the interface, and nobody finds out until a user cannot find the option. Generated, a new
field appears by itself — and one whose shape the generator does not understand raises by name
rather than disappearing from the panel. See ADR-020.

The cost is real and declared: a few fields have a closed domain the schema does not express —
language, log level, timezone — and they carry a control listed in `CHOICES`. The coverage test
accepts those because they are declared, not because they were forgotten.

### Deciding and displaying are separate on purpose

`PanelModel` holds no widgets. Which controls exist, what a value means, whether it validates and
what will be written are decided without a display, and therefore tested without one;
`ConfigPanel` is the widget tree and decides nothing.

Validation runs the section's own model over what the panel holds, so the rule lives in exactly
one place. A failure that names a field lands on that field. One that names none — the severity
thresholds, where neither value is wrong on its own — belongs to the section, which is why
CA-108.4 exists as a criterion separate from CA-108.3.

### The networks are a list, not four numbers

The four sources appear as an ordered list with arrows, and that list is the control for both
their `enabled` flag and their `priority`.

Four numeric fields that have to stay distinct would be asking the user to do the interface's job.
A list is what they are actually expressing.

Reordering declares a priority for **all four**, not only the ones that moved. Leaving some
unranked would let the list on screen and the list in the file drift apart the moment a later
version changed the declaration order — and the ordering rule itself lives in
[[src/vigia_eew/config.py#by_priority]], where both the panel and the source registry read it, so
there is only ever one list.

A network turned off stays in the list. Disabled is not deleted, and it has to be visible to be
turned back on.

## A door into the panel that is not the tray

[[src/vigia_eew/app.py#Application]]`.open_settings()` runs the panel on its own: no ingestion, no
bridge, no tray, one window and the loop that draws it. `vigia-eew --settings` is that mode, and
the desktop entry's *Settings* action is what invokes it in practice.

It exists because the tray entry is not reachable everywhere it appears. pystray selects its
backend when it is imported: AppIndicator — StatusNotifierItem over D-Bus — when PyGObject is
installed, and `_xorg`, a legacy XEmbed icon drawn with python-xlib, when it is not. A PyInstaller
build carries no PyGObject and no GTK typelibs, so a packaged agent always lands on `_xorg`.

Under X11 that backend is fine. Under GNOME/Wayland it fails in the one way that looks like
success: a shell extension still shows the icon, so the agent looks configurable, and the click
that should open the menu reaches nothing at all. That is the report this section comes from — the
icon was there, and "Configuración…" could not be got to.

Two consequences, both deliberate:

- [[src/vigia_eew/tray.py#menu_reachable]] names the case in the log instead of leaving an icon
  that silently does nothing. It is a warning, not a failure: the icon is still worth showing for
  its status text, and the agent must never die over its decoration (RF-34).
- The configuration stops depending on the tray at all. `--settings` needs no icon, no D-Bus and
  no extension, and the packaged desktop entry carries it as an action, so the path from "I
  installed it" to "I configured it" survives a session where the tray is decorative.

Making the tray menu itself work on GNOME would mean speaking StatusNotifierItem directly over
D-Bus — `dbus-fast` is already in the bundle for the toasts — which is ADR-010's bridge and a
feature of its own. This is the door, not the bridge.

## The panel's defaults are decisions, not leftovers

[[src/vigia_eew/notify/ui_scale.py#spans]] and its neighbours exist because a toolkit's defaults
used by omission were the wrong ones once already: the Tk panel opened as a tall narrow strip.

The panel is responsive (ADR-030): every field sits in a `ResponsiveRow` cell whose span is
`FIELD_COLUMNS` — one column on a narrow window, two from `md`, three from `xl` — so the same panel
reads on a laptop half-screen and on a wide monitor. The window opens at `PREFERRED_SIZE` and is
floored at `MINIMUM_SIZE`, where the labels stop fitting beside their controls. The alert window
is deliberately unaffected — it sizes its own type, and the one thing here that must never depend
on a default is the window whose whole job is to be impossible to miss.

The body scrolls and the footer does not. What fell off the bottom of an overfull panel was the
Save button, which is the difference between awkward and useless.

### The panel and the About window are not translated

`PANEL_LOCALE` is English and does not follow `[notification] language`.

The panel's field labels are derived from the configuration schema (ADR-020), and those names are
English by convention (RNF-10). Translating the frame around them would produce half a translation
— Spanish buttons over English field names — which reads worse than either language alone. The
alert, the toast and the tray menu are translated, because every word in them is written by hand
for the person reading it.

[[src/vigia_eew/notify/about.py#about_info]] follows the panel for the same reason, and carries
the licence and warranty notice the GPL asks an interactive program to state. Its version is read
from the installed package's metadata: a version typed into a label is wrong one release later,
and it is the first thing anybody reporting a bug is asked for.
